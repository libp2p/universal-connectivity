"""Topic, PubSub, and DHT discovery operations.

Subscription requests arrive from adapters on non-trio threads, so they are
validated here and queued for the trio worker that owns the chat room. The
read-side methods snapshot transport state for adapters without exposing
libp2p objects.
"""

from __future__ import annotations

import hashlib
import logging
import time
from queue import Empty, Full
from typing import Any

import trio
from libp2p.kad_dht.kad_dht import KadDHT

from ..chatroom import MAX_TOPIC_NAME_LENGTH, MAX_TOPICS, NON_CHAT_TOPICS
from ..constants import BOOTSTRAP_PEERS, DISCOVERY_SERVICE_TAG
from ..errors import (
    ConflictError,
    NotReadyError,
    NotFoundError,
    OperationError,
    ValidationError,
)

logger = logging.getLogger("app.services.discovery")


def _topic_to_dht_key(topic: str) -> str:
    """Multihash hex for a topic, matching go-libp2p's ``nsToCid``.

    go-libp2p's ``routing.Advertise``/``FindPeers`` translate a namespace with
    ``cid.NewCidV1(cid.Raw, multihash.Sum(ns, SHA2_256, -1))``, so the DHT key is
    the bare SHA-256 multihash. ``KadDHT.provide``/``find_providers`` hex-decode
    a hex string into those same bytes.
    """
    digest = hashlib.sha256(topic.encode("utf-8")).digest()
    # 0x12 = sha2-256, 0x20 = 32 bytes length
    mh = bytes([0x12, len(digest)]) + digest
    return mh.hex()


# rust-peer announces itself with ``kad.start_providing(RecordKey::new(
# "universal-connectivity/0.1.0"))``, i.e. the raw UTF-8 bytes of its agent
# string. Providing and searching that key here is what makes py-peer visible to
# rust-peer's provider lookup.
RUST_DISCOVERY_KEY = "universal-connectivity/0.1.0"


class DiscoveryService:
    """Topic subscription and network-topology queries."""

    def __init__(
        self,
        engine: Any,
        storage: Any = None,
        messaging: Any = None,
        notifications: Any = None,
        connections: Any = None,
    ) -> None:
        self._engine = engine
        self._storage = storage
        self._messaging = messaging
        self._notifications = notifications
        self._connections = connections
        self._dial_cooldown: dict[str, float] = {}

    @property
    def engine(self) -> Any:
        return self._engine

    # ------------------------------------------------------------------ #
    #  Topic views
    # ------------------------------------------------------------------ #
    def _subscribed_topics(self) -> set[str]:
        if self._messaging is not None:
            return self._messaging.subscribed_topics()
        chat_room = getattr(self._engine, "chat_room", None)
        return set(chat_room.get_subscribed_topics()) if chat_room else set()

    def topics(self) -> dict[str, Any]:
        if self._storage is not None:
            return self._storage.topics()
        return self._engine.get_all_topics_with_info()

    def topic_info(self, topic: str) -> dict[str, Any]:
        topics = self.topics()
        if topic not in topics:
            raise NotFoundError(f"Topic '{topic}' not found or not subscribed.")
        return {"topic": topic, **topics[topic]}

    def subscribe(self, topic: str) -> dict[str, Any]:
        """Queue a subscription request after enforcing app-level limits."""
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot queue a subscription.")
        if not isinstance(topic, str) or not topic.strip():
            raise ValidationError("'topic' field is required.")
        topic = topic.strip()
        if topic in NON_CHAT_TOPICS:
            raise ValidationError("That topic name is reserved for protocol use.")
        already = self._subscribed_topics()
        if topic in already:
            raise ConflictError(f"Already subscribed to topic '{topic}'.")
        if len(already) >= MAX_TOPICS:
            raise ConflictError(f"Topic limit reached ({MAX_TOPICS}).")
        if not self.queue_subscription(topic):
            raise OperationError("Failed to queue subscription.")
        return {
            "message": f"Subscription request queued for '{topic}'",
            "topic": topic,
        }

    def queue_subscription(self, topic_name: str) -> bool:
        """Validate and queue a topic subscription (thread-safe)."""
        engine = self._engine
        chat_room = getattr(engine, "chat_room", None)
        if not chat_room or not getattr(engine, "running", False):
            logger.warning(
                "Cannot subscribe to topic: chat room not ready or service not running"
            )
            return False
        if not isinstance(topic_name, str) or not topic_name:
            logger.warning("Cannot subscribe to an empty/non-string topic")
            return False
        if len(topic_name) > MAX_TOPIC_NAME_LENGTH:
            logger.warning(
                f"Cannot subscribe to oversized topic "
                f"({len(topic_name)} > {MAX_TOPIC_NAME_LENGTH} chars)"
            )
            return False
        if topic_name in NON_CHAT_TOPICS:
            logger.warning(f"Cannot subscribe to reserved topic: {topic_name}")
            return False
        if len(self._subscribed_topics()) >= MAX_TOPICS:
            logger.warning(f"Cannot subscribe to topic: limit {MAX_TOPICS} reached")
            return False

        queue = getattr(engine, "topic_subscription_queue", None)
        if queue is None:
            logger.warning("Topic subscription queue is not ready")
            return False
        try:
            queue.sync_q.put_nowait(
                {"topic": topic_name, "timestamp": time.time()}
            )
            logger.info(f"Queued subscription request for topic: {topic_name}")
            return True
        except Full:
            logger.warning("Topic subscription queue is full; dropping request")
            return False
        except Exception as e:
            logger.error(f"Failed to queue topic subscription: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Workers
    # ------------------------------------------------------------------ #
    async def process_topic_subscriptions(self) -> None:
        """Process topic subscription requests from adapters."""
        while getattr(self._engine, "running", False):
            queue = getattr(self._engine, "topic_subscription_queue", None)
            if queue is None:
                await trio.sleep(0.1)
                continue
            try:
                try:
                    subscription_data = queue.sync_q.get_nowait()
                    if subscription_data and "topic" in subscription_data:
                        topic_name = subscription_data["topic"]

                        if self._engine.chat_room and self._engine.running:
                            success = await self._engine.chat_room.subscribe_to_topic(
                                topic_name
                            )
                            if success:
                                logger.info(
                                    f"Successfully subscribed to topic: {topic_name}"
                                )
                                if self._notifications is not None:
                                    self._notifications.publish_event(
                                        "topic_subscribed", {"topic": topic_name}
                                    )
                                    await self._notifications.system(
                                        f"Subscribed to topic: {topic_name}"
                                    )
                            else:
                                logger.warning(
                                    f"Failed to subscribe to topic: {topic_name}"
                                )
                                await self._system(
                                    f"Failed to subscribe to topic: {topic_name}"
                                )
                        else:
                            logger.warning(
                                "Cannot subscribe to topic: chat room not ready"
                            )
                            await self._system(
                                "Cannot subscribe to topic: chat room not ready"
                            )

                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing topic subscription: {e}")
                    await trio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in topic subscription processing: {e}")
                await trio.sleep(0.1)

    # ------------------------------------------------------------------ #
    #  PubSub snapshots
    # ------------------------------------------------------------------ #
    def mesh(self) -> dict[str, list[str]]:
        """Snapshot GossipSub mesh, retrying on concurrent modification."""
        gossipsub = getattr(self._engine, "gossipsub", None)
        if not gossipsub:
            return {}
        mesh = getattr(gossipsub, "mesh", {})
        for _ in range(3):
            try:
                return {
                    topic: [str(p) for p in peers]
                    for topic, peers in mesh.items()
                }
            except RuntimeError:
                continue
        return {}

    def mesh_peers(self, topic: str) -> list[str]:
        return list(self.mesh().get(topic, []))

    def fanout(self) -> dict[str, list[str]]:
        """Snapshot GossipSub fanout, retrying on concurrent modification."""
        gossipsub = getattr(self._engine, "gossipsub", None)
        if not gossipsub:
            return {}
        fanout = getattr(gossipsub, "fanout", {})
        for _ in range(3):
            try:
                return {
                    topic: [str(p) for p in peers]
                    for topic, peers in fanout.items()
                }
            except RuntimeError:
                continue
        return {}

    def pubsub_peers(self) -> list[str]:
        """Snapshot pubsub peers, retrying if the live dict changes mid-copy."""
        pubsub = getattr(self._engine, "pubsub", None)
        if not pubsub:
            return []
        for _ in range(3):
            try:
                return [str(p) for p in pubsub.peers.keys()]
            except RuntimeError:
                continue
        return []

    def subscriptions(self) -> list[str]:
        if self._messaging is not None:
            return sorted(self._messaging.all_pubsub_topics())
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is None:
            return []
        return sorted(chat_room.get_all_subscriptions())

    def gossipsub_config(self) -> dict[str, Any]:
        gossipsub = self._engine.gossipsub
        return {
            "degree": getattr(gossipsub, "degree", None),
            "degree_low": getattr(gossipsub, "degree_low", None),
            "degree_high": getattr(gossipsub, "degree_high", None),
            "gossip_window": getattr(gossipsub, "gossip_window", None),
            "gossip_history": getattr(gossipsub, "gossip_history", None),
            "heartbeat_interval": getattr(gossipsub, "heartbeat_interval", None),
            "heartbeat_initial_delay": getattr(
                gossipsub, "heartbeat_initial_delay", None
            ),
            "protocols": [str(p) for p in getattr(gossipsub, "protocols", [])],
        }

    # ------------------------------------------------------------------ #
    #  DHT
    # ------------------------------------------------------------------ #
    def _require_dht(self) -> KadDHT:
        dht = getattr(self._engine, "dht", None)
        if not dht:
            raise NotReadyError("DHT is not initialised.")
        return dht

    def dht_status(self) -> dict[str, Any]:
        dht = self._require_dht()
        try:
            routing_table_size = len(list(dht.routing_table.get_peer_ids()))
        except Exception:
            routing_table_size = -1
        mode_val = getattr(dht, "mode", None)
        mode_str = str(getattr(mode_val, "name", mode_val))
        return {
            "mode": mode_str,
            "random_walk_enabled": getattr(dht, "enable_random_walk", False),
            "routing_table_size": routing_table_size,
        }

    def dht_peers(self) -> list[str]:
        dht = self._require_dht()
        try:
            return [str(peer) for peer in dht.routing_table.get_peer_ids()]
        except Exception as exc:  # pragma: no cover - library failure path
            raise OperationError(f"Could not read routing table: {exc}") from exc

    def bootstrap(self) -> dict[str, Any]:
        """Re-trigger bootstrap dials. Returns queued/total counts."""
        queued = 0
        for addr in BOOTSTRAP_PEERS:
            try:
                if self._connections is not None:
                    accepted = self._connections.queue_connection(addr)
                else:
                    accepted = self._engine.connect_to_peer(addr)
                if accepted:
                    queued += 1
            except Exception:
                logger.debug(
                    "Bootstrap dial queueing failed for %s", addr, exc_info=True
                )
        return {
            "message": f"Queued connections to {queued} bootstrap peers.",
            "bootstrap_peers_count": queued,
        }

    async def run_dht_discovery(self) -> None:
        """Periodic background task to provide and discover UC peers on Kademlia DHT."""
        while not getattr(self._engine, "ready", False):
            await trio.sleep(1)

        await trio.sleep(5)
        logger.info("🧭 Starting Kademlia DHT peer discovery worker")

        dht_key_hex = _topic_to_dht_key(DISCOVERY_SERVICE_TAG)
        rust_key = RUST_DISCOVERY_KEY

        last_provide_time = 0.0
        PROVIDE_INTERVAL = 120.0
        SEARCH_INTERVAL = 30.0
        TARGET_PUBSUB_PEERS = 8

        while getattr(self._engine, "running", False):
            try:
                now = time.time()
                dht = getattr(self._engine, "dht", None)
                host = getattr(self._engine, "host", None)

                if dht is not None and host is not None:
                    # 1. Periodically announce our node as a provider
                    if now - last_provide_time >= PROVIDE_INTERVAL:
                        try:
                            await dht.provide(dht_key_hex)
                            await dht.provide(rust_key)
                            last_provide_time = now
                            logger.info(
                                "📢 Advertised universal-connectivity provider records on DHT"
                            )
                        except Exception as exc:
                            logger.debug("DHT provide error: %s", exc)

                    # 2. Check pubsub peer count; if low, search for providers and restore from peerstore/routing table
                    current_pubsub_peers = self.pubsub_peers()
                    if len(current_pubsub_peers) < TARGET_PUBSUB_PEERS:
                        logger.info(
                            "PubSub peer count (%d) below target (%d); querying DHT providers and restoring peers...",
                            len(current_pubsub_peers),
                            TARGET_PUBSUB_PEERS,
                        )
                        my_id = str(host.get_id())
                        connected = {
                            str(p) for p in host.get_connected_peers()
                        }

                        # Evict expired dial cooldowns
                        self._dial_cooldown = {
                            pid: exp
                            for pid, exp in self._dial_cooldown.items()
                            if exp > now
                        }

                        dial_count = 0

                        # A. Query DHT provider records
                        try:
                            providers = await dht.find_providers(
                                dht_key_hex, count=20
                            )
                            try:
                                rust_providers = await dht.find_providers(
                                    rust_key, count=20
                                )
                            except Exception:
                                rust_providers = []
                            all_providers = providers + rust_providers

                            for pinfo in all_providers:
                                pid = str(pinfo.peer_id)
                                if (
                                    pid == my_id
                                    or pid in connected
                                    or pid in self._dial_cooldown
                                ):
                                    continue
                                if pinfo.addrs:
                                    host.get_peerstore().add_addrs(
                                        pinfo.peer_id, pinfo.addrs, ttl=3600
                                    )
                                    # Sort to prefer public/routable addresses
                                    sorted_addrs = sorted(
                                        pinfo.addrs,
                                        key=lambda a: (
                                            1
                                            if "/ip4/127." in str(a)
                                            or "/ip6/::1" in str(a)
                                            or "/ip4/192.168." in str(a)
                                            or "/ip4/10." in str(a)
                                            else 0
                                        ),
                                    )
                                    best_addr = sorted_addrs[0]
                                    addr_str = str(best_addr)
                                    if f"/p2p/{pid}" not in addr_str:
                                        addr_str = f"{addr_str}/p2p/{pid}"
                                    if self._connections is not None and self._connections.queue_connection(
                                        addr_str
                                    ):
                                        self._dial_cooldown[pid] = now + 45.0
                                        dial_count += 1
                        except Exception as exc:
                            logger.debug("DHT find_providers error: %s", exc)

                        # B. Restore from known peerstore peers if still below target
                        if len(current_pubsub_peers) + dial_count < TARGET_PUBSUB_PEERS:
                            try:
                                peerstore = host.get_peerstore()
                                for peer_id in peerstore.peers_with_addrs():
                                    pid = str(peer_id)
                                    if (
                                        pid == my_id
                                        or pid in connected
                                        or pid in self._dial_cooldown
                                    ):
                                        continue
                                    addrs = peerstore.addrs(peer_id)
                                    if not addrs:
                                        continue
                                    sorted_addrs = sorted(
                                        addrs,
                                        key=lambda a: (
                                            1
                                            if "/ip4/127." in str(a)
                                            or "/ip6/::1" in str(a)
                                            or "/ip4/192.168." in str(a)
                                            or "/ip4/10." in str(a)
                                            else 0
                                        ),
                                    )
                                    best_addr = sorted_addrs[0]
                                    addr_str = str(best_addr)
                                    if f"/p2p/{pid}" not in addr_str:
                                        addr_str = f"{addr_str}/p2p/{pid}"
                                    if self._connections is not None and self._connections.queue_connection(
                                        addr_str
                                    ):
                                        self._dial_cooldown[pid] = now + 45.0
                                        dial_count += 1
                                        if (
                                            len(current_pubsub_peers) + dial_count
                                            >= TARGET_PUBSUB_PEERS
                                        ):
                                            break
                            except Exception as exc:
                                logger.debug("Peerstore reconnect error: %s", exc)

                        if dial_count > 0:
                            logger.info(
                                "🧭 Queued connections to %d peers for PubSub mesh recovery",
                                dial_count,
                            )

                    # 3. Fallback: if pubsub peers dropped critically low (< 2), trigger bootstrap dials
                    if len(current_pubsub_peers) < 2:
                        logger.info(
                            "PubSub peers critically low (%d); re-triggering bootstrap dials",
                            len(current_pubsub_peers),
                        )
                        self.bootstrap()

            except trio.Cancelled:
                break
            except Exception as exc:
                logger.warning("Error in DHT discovery worker: %s", exc)

            await trio.sleep(SEARCH_INTERVAL)

    async def _system(self, message: str) -> None:
        if self._notifications is not None:
            await self._notifications.system(message)
