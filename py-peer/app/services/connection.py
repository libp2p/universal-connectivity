"""Peer dialling, configured connection setup, and connection state."""

from __future__ import annotations

import logging
from queue import Empty, Full
from typing import Any

import multiaddr
import trio
from libp2p.peer.peerinfo import info_from_p2p_addr

from ..errors import NotReadyError, OperationError, ValidationError

logger = logging.getLogger("app.services.connection")


class ConnectionService:
    """Queue outbound dials, run configured dials, and inspect state."""

    def __init__(
        self,
        engine: Any,
        addresses: Any = None,
        notifications: Any = None,
    ) -> None:
        self._engine = engine
        self._addresses = addresses
        self._notifications = notifications

    @property
    def engine(self) -> Any:
        return self._engine

    @staticmethod
    def validate_multiaddr(value: str) -> str:
        """Validate a dial target and return it unchanged."""
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("'multiaddr' field is required.")
        value = value.strip()
        try:
            info_from_p2p_addr(multiaddr.Multiaddr(value))
        except Exception as exc:
            raise ValidationError(
                "Invalid multiaddr — expected a valid libp2p address ending with /p2p/<peer-id>.",
                detail=str(exc),
            ) from exc
        return value

    def _normalize_dial_addr(self, value: str) -> str:
        if self._addresses is not None:
            return self._addresses.normalize_dial_addr(value)
        normalized = value
        if "/ip4/0.0.0.0/" in normalized:
            normalized = normalized.replace(
                "/ip4/0.0.0.0/", "/ip4/127.0.0.1/"
            )
        if "/ip6/::/" in normalized:
            normalized = normalized.replace("/ip6/::/", "/ip6/::1/")
        return normalized

    def connect(self, maddr: str) -> dict[str, Any]:
        """Queue a dial request. Returns a small acknowledgement payload."""
        target = self.validate_multiaddr(maddr)
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot queue a connection.")
        if not self.queue_connection(target):
            raise OperationError("Failed to queue connection request.")
        return {"message": "Connection request queued", "multiaddr": target}

    def queue_connection(self, multiaddr_str: str) -> bool:
        """Queue a dial request (thread-safe)."""
        engine = self._engine
        if not engine.host or not getattr(engine, "running", False):
            logger.warning(
                "Cannot connect to peer: host not ready or service not running"
            )
            return False

        queue = getattr(engine, "peer_connection_queue", None)
        if queue is None:
            logger.warning("Cannot connect to peer: connection queue not ready")
            return False

        try:
            # 0.0.0.0 is a bind address, not a dial address — rewrite to loopback.
            target = self._normalize_dial_addr(multiaddr_str)
            queue.sync_q.put_nowait(target)
            logger.info(f"Queued peer connection request: {target}")
            return True
        except Full:
            logger.warning("Peer connection queue is full; dropping request")
            return False
        except Exception as e:
            logger.error(f"Failed to queue peer connection: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Configured dials
    # ------------------------------------------------------------------ #
    async def setup_connections(self) -> None:
        """Connect to the peers supplied on the command line."""
        engine = self._engine
        if not engine.connect_addrs:
            return

        for addr_str in engine.connect_addrs:
            try:
                logger.info(f"🔗 Attempting to connect to: {addr_str}")
                maddr = multiaddr.Multiaddr(self._normalize_dial_addr(addr_str))
                info = info_from_p2p_addr(maddr)
                logger.info(
                    f"🔗 Parsed peer info - ID: {info.peer_id}, Addrs: {info.addrs}"
                )

                existing_conns = engine.host.get_network().connections.get(
                    info.peer_id
                )
                if existing_conns:
                    logger.info(
                        f"✅ Already connected to peer: {info.peer_id}, "
                        "skipping connection attempt"
                    )
                    continue

                logger.info(f"🔗 Initiating connection to peer: {info.peer_id}")
                await engine.host.connect(info)
                logger.info(f"✅ TCP connection established to peer: {info.peer_id}")

                # Wait for protocol negotiation before inspecting it.
                await trio.sleep(3)

                logger.info(
                    f"🔍 Starting protocol inspection for peer: {info.peer_id}"
                )
                await self.inspect_peer_protocols(info.peer_id)

                try:
                    swarm = engine.host.get_network()
                    if (
                        hasattr(swarm, "connections")
                        and info.peer_id in swarm.connections
                    ):
                        connections = [swarm.connections[info.peer_id]]
                        logger.info(
                            f"📊 Active connections to peer {info.peer_id}: "
                            f"{len(connections)}"
                        )
                    else:
                        logger.info(
                            f"📊 No direct connection info available for peer "
                            f"{info.peer_id}"
                        )
                except Exception as conn_err:
                    logger.warning(
                        f"⚠️  Could not check connection status: {conn_err}"
                    )

                logger.info("⏳ Waiting for PubSub protocol negotiation...")
                await trio.sleep(3)
                await self.check_pubsub_status(info.peer_id)

                await self._system(f"Connected to peer: {str(info.peer_id)}")

            except Exception as e:
                logger.error(f"❌ Failed to connect to {addr_str}: {e}")
                await self._system(f"Failed to connect to {addr_str}: {e}")

    async def inspect_peer_protocols(self, peer_id: Any) -> None:
        """Inspect and log all protocols supported by a peer."""
        try:
            logger.info(f"🔍 Checking peerstore for peer: {peer_id}")
            peerstore = self._engine.host.get_peerstore()

            try:
                if hasattr(peerstore, "get_protocols"):
                    protocols = peerstore.get_protocols(peer_id)
                elif hasattr(peerstore, "protocols"):
                    protocols = peerstore.protocols(peer_id)
                else:
                    logger.info(
                        f"✅ Successfully connected to peer {peer_id}"
                    )
                    logger.info(
                        "🔍 Protocol inspection not available in this "
                        "py-libp2p version"
                    )
                    return

                if protocols:
                    logger.info(
                        f"📋 Peer {peer_id} supports {len(protocols)} protocols:"
                    )
                    for i, protocol in enumerate(protocols, 1):
                        logger.info(f"  {i}: {protocol}")
                        if (
                            "meshsub" in str(protocol)
                            or "gossipsub" in str(protocol)
                        ):
                            logger.info(f"  🎯 Found PubSub protocol: {protocol}")
                else:
                    logger.info(
                        f"📋 No protocols found for peer {peer_id} yet "
                        "(may still be negotiating)"
                    )

            except Exception as proto_err:
                logger.info(f"🔍 Protocol details not accessible: {proto_err}")
                logger.info(f"✅ Peer {peer_id} connected successfully")

        except Exception as e:
            logger.warning(f"⚠️  Error inspecting peer protocols: {e}")
            logger.info(f"✅ Peer {peer_id} connected successfully")

    async def check_pubsub_status(self, peer_id: Any) -> None:
        """Check the PubSub connection status with a specific peer."""
        try:
            logger.info(f"🔍 Checking PubSub status for peer: {peer_id}")
            pubsub = self._engine.pubsub

            pubsub_peers = list(pubsub.peers.keys())
            logger.info(f"📡 Total PubSub peers: {len(pubsub_peers)}")
            for i, p in enumerate(pubsub_peers, 1):
                logger.info(f"  PubSub peer {i}: {p}")

            if peer_id in pubsub.peers:
                logger.info(f"✅ Peer {peer_id} is in PubSub mesh")

                if hasattr(pubsub, "router") and hasattr(pubsub.router, "mesh"):
                    mesh = pubsub.router.mesh
                    logger.info("🕸️  GossipSub mesh status:")
                    logger.info(f"    Mesh topics: {list(mesh.keys())}")
                    for topic, topic_peers in mesh.items():
                        logger.info(
                            f"    Topic '{topic}': {len(topic_peers)} peers"
                        )
                        if peer_id in topic_peers:
                            logger.info(
                                f"    ✅ Peer {peer_id} is in mesh for "
                                f"topic '{topic}'"
                            )
                        else:
                            logger.warning(
                                f"    ❌ Peer {peer_id} is NOT in mesh for "
                                f"topic '{topic}'"
                            )
            else:
                logger.warning(f"❌ Peer {peer_id} is NOT in PubSub mesh")
                logger.info("🔧 Possible reasons:")
                logger.info("  1. PubSub protocol negotiation failed")
                logger.info(
                    "  2. Peer doesn't support compatible GossipSub version"
                )
                logger.info("  3. Network issues preventing PubSub handshake")

        except Exception as e:
            logger.error(f"❌ Error checking PubSub status: {e}")

    # ------------------------------------------------------------------ #
    #  Worker
    # ------------------------------------------------------------------ #
    async def process_peer_connections(self) -> None:
        """Process peer connection requests from adapters."""
        while getattr(self._engine, "running", False):
            queue = getattr(self._engine, "peer_connection_queue", None)
            if queue is None:
                await trio.sleep(0.1)
                continue
            try:
                try:
                    multiaddr_str = queue.sync_q.get_nowait()
                    if multiaddr_str:
                        logger.info(
                            f"Processing peer connection request: {multiaddr_str}"
                        )
                        try:
                            maddr = multiaddr.Multiaddr(
                                self._normalize_dial_addr(multiaddr_str)
                            )
                            peer_info = info_from_p2p_addr(maddr)

                            if peer_info:
                                logger.info(
                                    f"Attempting to connect to peer: "
                                    f"{peer_info.peer_id}"
                                )
                                await self._engine.host.connect(peer_info)
                                logger.info(
                                    f"✅ Successfully connected to peer: "
                                    f"{peer_info.peer_id}"
                                )
                                await self._system(
                                    f"Connected to peer: {peer_info.peer_id}"
                                )
                            else:
                                logger.error(
                                    "Could not extract peer info from multiaddress: "
                                    f"{multiaddr_str}"
                                )
                                await self._system("Invalid multiaddress format")

                        except Exception as e:
                            logger.error(
                                f"Failed to connect to peer {multiaddr_str}: {e}"
                            )
                            await self._system(f"Connection failed: {str(e)}")

                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing peer connection: {e}")
                    await trio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in peer connection processing: {e}")
                await trio.sleep(0.1)

    def is_connected(self, peer_id: str) -> bool:
        try:
            return str(peer_id) in {
                str(peer) for peer in self._engine.host.get_connected_peers()
            }
        except Exception:
            return False

    async def _system(self, message: str) -> None:
        if self._notifications is not None:
            await self._notifications.system(message)
