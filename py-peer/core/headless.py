"""
Headless Service for Universal Connectivity Python Peer

This module owns the libp2p transport (host, pubsub, DHT, bitswap) and the
process lifecycle. Application behaviour lives in ``app.services``; the engine
receives one ServiceBundle from ``ApplicationRuntime`` and only calls into it.
"""

from __future__ import annotations

import logging
import os
import threading
import traceback
from typing import Any, Callable, Dict, List, Set

import janus
import trio
from libp2p import new_host, IHost
from libp2p.bitswap import BitswapClient, MemoryBlockStore
from libp2p.bitswap.dag import MerkleDag
from libp2p.discovery.bootstrap import BootstrapDiscovery
from libp2p.host.exceptions import StreamFailure
from libp2p.host.ping import ID as PING_PROTOCOL_ID, PingService
import libp2p.identity.identify.identify as identify_mod
from libp2p.identity.identify.identify import (
    ID as IDENTIFY_PROTOCOL_ID,
    identify_handler_for,
)

# Align identify agent version with universal-connectivity standard so
# go-peer, rust-peer, and other peers recognise py-peer as a UC node.
identify_mod.AGENT_VERSION = "universal-connectivity/0.1.0"
from libp2p.kad_dht.kad_dht import DHTMode, KadDHT
from libp2p.network.config import ConnectionConfig
from libp2p.peer.peerinfo import PeerInfo
from libp2p.protocol_muxer.exceptions import MultiselectClientError
from libp2p.pubsub.gossipsub import (
    PROTOCOL_ID,
    PROTOCOL_ID_V11,
    PROTOCOL_ID_V12,
    GossipSub,
)
from libp2p.pubsub.pubsub import Pubsub
from libp2p.tools.anyio_service import background_trio_service

from .constants import (
    BOOTSTRAP_PEERS,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_PORT,
    DISCOVERY_SERVICE_TAG,
    FILE_MESSAGE_PREFIX,
    MAX_FILE_QUEUE,
    MAX_LEGACY_QUEUE,
    MAX_OUTGOING_QUEUE,
    MAX_REQUEST_QUEUE,
    MAX_TOPIC_MESSAGES,
)

logger = logging.getLogger("headless")

# Constants retained here for backwards-compatible imports.
PROTOCOL_ID_LIST = [PROTOCOL_ID, PROTOCOL_ID_V11, PROTOCOL_ID_V12]

__all__ = [
    "BOOTSTRAP_PEERS",
    "DEFAULT_DOWNLOAD_DIR",
    "DEFAULT_PORT",
    "DISCOVERY_SERVICE_TAG",
    "FILE_MESSAGE_PREFIX",
    "HeadlessService",
    "MAX_FILE_QUEUE",
    "MAX_LEGACY_QUEUE",
    "MAX_OUTGOING_QUEUE",
    "MAX_REQUEST_QUEUE",
    "MAX_TOPIC_MESSAGES",
    "PROTOCOL_ID_LIST",
    "filter_compatible_peer_info",
]


def filter_compatible_peer_info(peer_info: PeerInfo) -> bool:
    """Filter peer info to check if it has compatible addresses across supported transports."""
    if not hasattr(peer_info, "addrs") or not peer_info.addrs:
        return False

    supported_markers = (
        "/tcp/",
        "/ws",
        "/wss",
        "/quic-v1",
        "/quic",
    )
    for addr in peer_info.addrs:
        addr_str = str(addr)
        if any(marker in addr_str for marker in supported_markers):
            if "/webtransport" not in addr_str and "/webrtc" not in addr_str:
                return True
    return False


class HeadlessService:
    """Manage the libp2p transport and delegate application work to services."""

    def __init__(
        self,
        nickname: str,
        port: int = 0,
        connect_addrs: List[str] | None = None,
        ui_mode: bool = False,
        strict_signing: bool = True,
        seed: str | None = None,
        topic: str | None = None,
        announce_host: str = "127.0.0.1",
        listen_addrs: List[str] | None = None,
        announce_addrs: List[str] | None = None,
        message_store: Any = None,
        event_bus: Any = None,
        identity_path: str | None = None,
        services: Any = None,
        min_connections: int = 50,
        low_watermark: int = 400,
        high_watermark: int = 450,
        max_connections: int = 500,
    ):
        self.nickname = nickname
        self.port = port if port != 0 else 4001
        self.connect_addrs = connect_addrs or []
        self.min_connections = min_connections
        self.low_watermark = low_watermark
        self.high_watermark = high_watermark
        self.max_connections = max_connections

        # Address model (deliberately separate concepts):
        #   listen  : where sockets are opened. Default binds all IPv4
        #             interfaces on the configured port.
        #   announce: what host.get_addrs() shares with other peers. Explicit
        #             announce_addrs win; otherwise wildcard listen addresses
        #             are rewritten to announce_host (0.0.0.0 is never
        #             advertised because it is not a dial target).
        #   observed: addresses reported by Identify and recorded by
        #             py-libp2p's ObservedAddrManager, then merged into
        #             get_addrs() by the library.
        self.listen_addrs = list(listen_addrs) if listen_addrs else None
        self.announce_addrs = list(announce_addrs) if announce_addrs else None
        self.announce_host = announce_host
        self.event_bus: Any = event_bus  # optional app.events.EventBus; additive
        self.ui_mode = ui_mode
        self.strict_signing = strict_signing
        self.seed = seed or None
        self.identity_path = (
            os.path.abspath(os.path.expanduser(identity_path))
            if identity_path
            else None
        )
        self.identity_source = None  # seed | persisted | created | ephemeral
        self.topic = topic

        # libp2p components (transport only)
        self.host: IHost | None = None
        self.pubsub: Pubsub | None = None
        self.gossipsub: GossipSub | None = None
        self.dht: KadDHT | None = None
        self.ping_service: PingService | None = None
        self.chat_room: Any = None

        # Bitswap components for file sharing
        self.bitswap_client: BitswapClient | None = None
        self.merkle_dag: MerkleDag | None = None
        self.block_store: MemoryBlockStore = MemoryBlockStore()

        # Service state
        self.running = False
        self.ready = False
        self.full_multiaddr: str | None = None
        self.full_multiaddrs: list[str] = []
        self.transport_addrs: list[str] = []

        # Communication with UI (created in start(); services read them
        # dynamically, so constructing services earlier is safe).
        self.message_queue: janus.Queue[Any] | None = None
        self.system_queue: janus.Queue[Any] | None = None
        self.outgoing_queue: janus.Queue[Any] | None = None
        self.topic_subscription_queue: janus.Queue[Any] | None = None
        self.peer_connection_queue: janus.Queue[Any] | None = None
        self.file_share_queue: janus.Queue[Any] | None = None
        self.file_download_queue: janus.Queue[Any] | None = None

        # Storage and file destination are engine-owned configuration.
        self.message_store: Any = message_store
        self.download_dir = DEFAULT_DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)

        # Events for synchronization. stop_event must be settable from the
        # Tornado/API thread, so it is a threading.Event rather than a trio.Event.
        self.ready_event = trio.Event()
        self.stop_event = threading.Event()

        self.on_stopped: Callable[[], None] | None = None
        self.failed = False

        # Lifecycle ownership. start() may run at most once per instance, and
        # the async teardown runs exactly once from start()'s finally block,
        # on the trio thread that owns the host.
        self._started = False
        self._shutdown_done = False

        # Injected by ApplicationRuntime so the transport engine stays free of
        # application-layer imports.
        self.services: Any = services

        if not ui_mode:
            logger.info(
                f"HeadlessService initialized - nickname: {nickname}, "
                f"port: {self.port}, strict_signing: {strict_signing}"
            )

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        """Start the headless service."""
        services = self.services
        if services is None:
            raise RuntimeError(
                "HeadlessService requires an injected ServiceBundle; "
                "construct it through ApplicationRuntime."
            )
        if self._started:
            raise RuntimeError(
                "HeadlessService.start() has already been called on this instance"
            )
        self._started = True
        logger.info("Starting headless service...")

        try:
            logger.debug("Creating message queues...")
            self.message_queue = janus.Queue[Any](maxsize=MAX_LEGACY_QUEUE)
            self.system_queue = janus.Queue[Any](maxsize=MAX_LEGACY_QUEUE)
            self.outgoing_queue = janus.Queue[Any](maxsize=MAX_OUTGOING_QUEUE)
            self.topic_subscription_queue = janus.Queue[Any](maxsize=MAX_REQUEST_QUEUE)
            self.peer_connection_queue = janus.Queue[Any](maxsize=MAX_REQUEST_QUEUE)
            self.file_share_queue = janus.Queue[Any](maxsize=MAX_FILE_QUEUE)
            self.file_download_queue = janus.Queue[Any](maxsize=MAX_FILE_QUEUE)
            logger.debug("Message queues created successfully")

            await services.notifications.system(
                "Headless service starting..."
            )
            await self._run_service()

        except Exception as e:
            self.failed = True
            logger.error(f"Failed to start headless service: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise
        finally:
            # Perform teardown on the trio thread that owns the host, whatever
            # the exit path (stop requested, startup error, or cancellation).
            # pyrefly: ignore
            with trio.CancelScope(shield=True):
                await self._shutdown_async()
            self.ready = False
            self.running = False
            if self.on_stopped:
                try:
                    self.on_stopped()
                except Exception:
                    logger.exception("Error in on_stopped callback")

    async def _run_service(self) -> None:
        """Run the main service loop: build transport, then start services."""
        services = self.services

        key_pair = services.identity.load_identity()

        # Resolve bind vs advertised addresses before creating the host. The
        # listen list is verified after host.run() starts the listeners; the
        # advertised list is derived from host.get_addrs() at the same point.
        listen_addrs = services.addresses.resolve_listen_addrs()
        explicit_announce = services.addresses.resolve_announce_addrs()
        addrs_factory = services.addresses.make_addrs_factory()

        services.addresses.warn_if_port_in_use(listen_addrs)

        config = ConnectionConfig(
            min_connections=self.min_connections,
            low_watermark=self.low_watermark,
            high_watermark=self.high_watermark,
            max_connections=self.max_connections,
            auto_connect_interval=5.0,
        )

        # Create libp2p host WITHOUT bootstrap nodes initially; bootstrap
        # dials happen after pubsub is running.
        host = new_host(
            key_pair=key_pair,
            connection_config=config,
            listen_addrs=listen_addrs,
            announce_addrs=explicit_announce or None,
            addrs_factory=addrs_factory,
        )
        self.host = host

        logger.info(
            "📋 Registering identify protocol handler (raw protobuf format "
            "for go-libp2p compatibility)"
        )
        identify_handler = identify_handler_for(
            host, use_varint_format=True
        )
        host.set_stream_handler(IDENTIFY_PROTOCOL_ID, identify_handler)
        logger.info(
            f"✅ Identify protocol handler registered for {IDENTIFY_PROTOCOL_ID}"
        )

        ping_service = PingService(host)
        self.ping_service = ping_service
        host.set_stream_handler(PING_PROTOCOL_ID, ping_service.handle_ping)
        logger.info(f"✅ Ping protocol handler registered for {PING_PROTOCOL_ID}")

        dht = KadDHT(host, DHTMode.SERVER, enable_random_walk=True)
        self.dht = dht
        logger.info("✅ DHT created with random walk enabled")

        logger.info(f"Host created with PeerID: {host.get_id()}")
        logger.info(
            "Configured listen address(es): "
            + ", ".join(str(addr) for addr in listen_addrs)
        )
        if explicit_announce:
            logger.info(
                "Using explicit announce address(es): "
                + ", ".join(str(addr) for addr in explicit_announce)
            )
        elif any(
            services.addresses.is_wildcard_addr(addr) for addr in listen_addrs
        ):
            logger.info(
                f"Wildcard listeners will be advertised as {self.announce_host!r} "
                "(configure --announce-host or --announce-addr to change)"
            )
        else:
            logger.info(
                "No wildcard listeners: advertised addresses are the concrete "
                "bound addresses from the host"
            )

        logger.info(f"📋 Configuring GossipSub with protocols: {PROTOCOL_ID_LIST}")
        logger.info(f"  Protocol 1: {PROTOCOL_ID}")
        logger.info(f"  Protocol 2: {PROTOCOL_ID_V11}")

        gossipsub = GossipSub(
            protocols=PROTOCOL_ID_LIST,
            degree=6,
            degree_low=4,
            degree_high=12,
            gossip_window=3,
            gossip_history=5,
            heartbeat_initial_delay=2.0,
            heartbeat_interval=5,
        )
        self.gossipsub = gossipsub
        logger.info("✅ GossipSub router created successfully")

        logger.info(
            f"🔐 Creating PubSub with strict_signing={self.strict_signing}"
        )
        pubsub = Pubsub(
            host, gossipsub, strict_signing=self.strict_signing
        )
        self.pubsub = pubsub
        logger.info("✅ PubSub service created successfully")

        bitswap = BitswapClient(host, self.block_store)
        self.bitswap_client = bitswap
        self.merkle_dag = MerkleDag(bitswap)
        logger.info("✅ Bitswap client and MerkleDag created for file sharing")

        async with host.run(listen_addrs=listen_addrs):
            services.addresses.verify_listeners(host, listen_addrs)
            services.addresses.refresh_advertised_addrs(host)
            logger.info("📡 Initializing PubSub, GossipSub, and DHT services...")
            try:
                async with background_trio_service(pubsub):
                    async with background_trio_service(gossipsub):
                        async with background_trio_service(dht):
                            logger.info(
                                "✅ Pubsub, GossipSub, and DHT services started."
                            )
                            await pubsub.wait_until_ready()
                            logger.info("✅ Pubsub ready and operational.")
                            logger.info(
                                "✅ DHT service started with random walk enabled."
                            )
                            if BOOTSTRAP_PEERS:
                                bootstrap = BootstrapDiscovery(
                                    host.get_network(), BOOTSTRAP_PEERS
                                )
                                await bootstrap.start()

                            # Join the chat room BEFORE connections so topics
                            # are subscribed when GossipSub negotiates.
                            await services.messaging.setup_chat_room()

                            await bitswap.start()
                            logger.info(
                                "✅ Bitswap client started for file sharing"
                            )

                            await services.connections.setup_connections()

                            self.ready = True
                            self.ready_event.set()
                            logger.info("✅ Headless service is ready")

                            async with trio.open_nursery() as nursery:
                                bitswap.set_nursery(nursery)
                                services.start_workers(nursery)
                                nursery.start_soon(self._ping_keepalive_worker)

                                await self._wait_for_stop()
                                nursery.cancel_scope.cancel()

            except (MultiselectClientError, StreamFailure) as e:
                # Core protocol failure, not a routine dial error: let the
                # supervisor restart the process instead of exiting cleanly.
                logger.error(f"The protocol negotiation failed: {e}")
                self.failed = True
                raise

    async def _wait_for_stop(self) -> None:
        """Poll the thread-safe stop signal without blocking the trio thread."""
        while not self.stop_event.is_set():
            await trio.sleep(0.1)
        logger.info("Stop signal received, shutting down...")
        self.running = False

    async def _ping_keepalive_worker(self) -> None:
        """Periodically ping connected peers to keep NAT mappings and connections alive."""
        while not self.stop_event.is_set():
            try:
                await trio.sleep(30)
                if self.stop_event.is_set():
                    break
                host = self.host
                ping_svc = self.ping_service
                if host is None or ping_svc is None or not self.ready:
                    continue
                connected = list(host.get_connected_peers())
                for peer in connected:
                    try:
                        with trio.move_on_after(5):
                            await ping_svc.ping(peer, ping_amt=1)
                    except Exception:
                        pass
            except trio.Cancelled:
                break
            except Exception as exc:
                logger.debug(f"Ping keepalive error: {exc}")

    def request_stop(self) -> None:
        """Ask the service to stop. Safe to call from any thread.

        This only signals intent. The trio thread that owns the host performs
        the actual teardown once, in ``start()``'s ``finally`` block.
        """
        if self.stop_event is not None:
            self.stop_event.set()

    async def _shutdown_async(self) -> None:
        """Tear down resources owned by the trio loop. Runs at most once."""
        if self._shutdown_done:
            return
        self._shutdown_done = True
        logger.info("Stopping headless service...")

        # Services own the chat room and per-client subscriber queues.
        try:
            await self.services.shutdown()
        except Exception:
            logger.exception("Error stopping application services")

        # libp2p's Pubsub allocates a ``LastSeenCache`` whose daemon cleanup
        # thread is not joined by the service context manager.
        pubsub = getattr(self, "pubsub", None)
        seen_messages = getattr(pubsub, "seen_messages", None)
        stop_cache = getattr(seen_messages, "stop", None)
        if stop_cache is not None:
            try:
                stop_cache()
            except Exception:
                logger.exception("Error stopping the pubsub seen-message cache")

        if self.bitswap_client:
            try:
                await self.bitswap_client.stop()
            except Exception:
                logger.exception("Error stopping Bitswap client")

        for queue in (
            self.message_queue,
            self.system_queue,
            self.outgoing_queue,
            self.topic_subscription_queue,
            self.peer_connection_queue,
            self.file_share_queue,
            self.file_download_queue,
        ):
            if queue:
                try:
                    queue.close()
                except Exception:
                    pass

        logger.info("Headless service stopped")

    async def stop(self) -> None:
        """Request shutdown (async for callers inside the trio loop)."""
        self.request_stop()

    # ------------------------------------------------------------------ #
    #  Delegates to application services
    # ------------------------------------------------------------------ #
    async def monitor_peers(self) -> None:
        await self.services.peers.monitor_peers()

    def send_message(self, message: str) -> bool:
        """Queue a message for the default chat topic (thread-safe)."""
        return self.services.messaging.enqueue(message)

    def send_message_to_topic(self, topic: str, message: str) -> bool:
        """Queue a message for a specific topic (thread-safe)."""
        return self.services.messaging.enqueue_to_topic(topic, message)

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for UI."""
        return self.services.peers.connection_info_dict()

    def get_subscribed_topics(self) -> Set[str]:
        """Get user-facing chat subscriptions (protocol topics excluded)."""
        return self.services.messaging.subscribed_topics()

    def get_all_pubsub_topics(self) -> Set[str]:
        """Get every pubsub subscription, including protocol-only topics."""
        return self.services.messaging.all_pubsub_topics()

    def get_shared_files(self) -> List[Dict[str, Any]]:
        return self.services.files.shared_files()

    def get_shared_file(self, cid: str) -> Any:
        return self.services.files.shared_file_raw(cid)

    def get_peer_info_cache_snapshot(self) -> Dict[str, Dict[str, Any]]:
        return self.services.identity.snapshot()

    def get_peer_info(self, peer_id: str) -> Any:
        return self.services.identity.raw_get(peer_id)

    def delete_peer_info(self, peer_id: str) -> bool:
        return self.services.identity.raw_delete(peer_id)

    def get_pubsub_peers(self) -> List[str]:
        return self.services.discovery.pubsub_peers()

    def get_gossipsub_mesh(self) -> Dict[str, List[str]]:
        return self.services.discovery.mesh()

    def get_gossipsub_fanout(self) -> Dict[str, List[str]]:
        return self.services.discovery.fanout()

    def subscribe_to_topic(self, topic_name: str) -> bool:
        return self.services.discovery.queue_subscription(topic_name)

    def connect_to_peer(self, multiaddr: str) -> bool:
        return self.services.connections.queue_connection(multiaddr)

    def share_file(self, file_path: str, topic: str) -> bool:
        return self.services.files.queue_share(file_path, topic)

    def download_file(self, file_cid: str, file_name: str = "unknown") -> bool:
        return self.services.files.queue_download(file_cid, file_name)

    def register_subscriber(self, kind: str = "message") -> Any:
        return self.services.notifications.register_subscriber(kind)

    def unregister_subscriber(self, kind: str, queue: Any) -> None:
        self.services.notifications.unsubscribe(kind, queue)

    def get_message_queue(self) -> Any:
        return self.message_queue

    def get_system_queue(self) -> Any:
        return self.system_queue

    def get_topic_messages(self, topic: str) -> List[Dict[str, Any]]:
        return self.services.storage.topic_messages(topic)

    def get_all_topics_with_info(self) -> Dict[str, Dict[str, Any]]:
        return self.services.storage.topics()

    def mark_topic_as_read(self, topic: str) -> None:
        self.services.storage.mark_read(topic)

    def get_unread_count(self, topic: str) -> int:
        return self.services.storage.unread(topic)

    def get_outgoing_queue(self) -> Any:
        return self.outgoing_queue

    async def get_peer_info_via_identify(self, peer_id: str) -> Any:
        return await self.services.identity.fetch_peer_info(peer_id)

    async def get_cached_peer_info(self, peer_id: str) -> Any:
        return await self.services.identity.cached_peer_info(peer_id)

    def get_public_key_for_peer(self, peer_id: str) -> Any:
        return self.services.identity.raw_public_key(peer_id)
