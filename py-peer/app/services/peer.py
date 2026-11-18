"""Peer identity, connection snapshots, and the peer monitor worker."""

from __future__ import annotations

import logging
from typing import Any

import trio
from libp2p.peer.id import ID

from ..errors import NotFoundError, ValidationError
from ..models import ConnectionSummary, PeerIdentity

logger = logging.getLogger("app.services.peer")


class PeerService:
    """Local identity plus read-only peer state."""

    def __init__(self, engine: Any, notifications: Any = None) -> None:
        self._engine = engine
        self._notifications = notifications
        self._known_connected_peers: set[str] = set()

    @property
    def engine(self) -> Any:
        return self._engine

    def identity(self) -> PeerIdentity:
        return PeerIdentity(
            peer_id=str(self._engine.host.get_id()),
            nickname=self._engine.nickname,
        )

    # ------------------------------------------------------------------ #
    #  Connection snapshots
    # ------------------------------------------------------------------ #
    def connection_info_dict(self) -> dict[str, Any]:
        """Engine-compatible connection snapshot (empty until ready)."""
        engine = self._engine
        if not getattr(engine, "ready", False):
            return {}

        chat_room = getattr(engine, "chat_room", None)
        if chat_room is not None:
            connected = {
                str(peer) for peer in chat_room.get_connected_peers()
            }
            peer_count = chat_room.get_peer_count()
        else:
            connected = set()
            peer_count = 0

        return {
            "peer_id": str(engine.host.get_id()) if getattr(engine, "host", None) else getattr(engine, "peer_id", ""),
            "nickname": engine.nickname,
            "multiaddr": engine.full_multiaddrs[0] if engine.full_multiaddrs else None,
            "multiaddrs": list(engine.full_multiaddrs),
            "listen_addrs": list(engine.transport_addrs),
            "connected_peers": connected,
            "peer_count": peer_count,
        }

    def connection_info(self) -> ConnectionSummary:
        info = self.connection_info_dict()
        return ConnectionSummary(
            peer_id=info.get("peer_id", ""),
            nickname=str(info.get("nickname") or self._engine.nickname),
            multiaddr=info.get("multiaddr"),
            multiaddrs=list(info.get("multiaddrs") or []),
            listen_addrs=list(info.get("listen_addrs") or []),
            connected_peers=sorted(
                str(peer) for peer in info.get("connected_peers", set())
            ),
        )

    def connected_peers(self) -> list[str]:
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is None:
            return []
        return sorted(str(peer) for peer in chat_room.get_connected_peers())

    def peer_count(self) -> int:
        chat_room = getattr(self._engine, "chat_room", None)
        return chat_room.get_peer_count() if chat_room else 0

    def listening_addrs(self) -> list[str]:
        return list(self._engine.transport_addrs)

    def advertised_addrs(self) -> list[str]:
        return list(self._engine.full_multiaddrs)

    def known_peers(self) -> list[str]:
        try:
            peerstore = self._engine.host.get_peerstore()
            return sorted(str(peer) for peer in peerstore.peers_with_addrs())
        except Exception as exc:  # pragma: no cover - library failure path
            raise ValidationError(f"Could not read peerstore: {exc}") from exc

    def peer_detail(self, peer_id: str) -> dict[str, Any]:
        """Return peerstore addresses for a peer ID."""
        try:
            pid = ID.from_base58(peer_id)
        except Exception as exc:
            raise ValidationError("Invalid peer ID.") from exc
        try:
            pinfo = self._engine.host.get_peerstore().peer_info(pid)
        except Exception as exc:
            raise NotFoundError(f"Peer not found: {exc}") from exc
        return {
            "peer_id": peer_id,
            "addrs": [str(addr) for addr in (pinfo.addrs or [])],
        }

    def is_connected(self, peer_id: str) -> bool:
        return peer_id in self.connected_peers()

    # ------------------------------------------------------------------ #
    #  Worker
    # ------------------------------------------------------------------ #
    async def monitor_peers(self) -> None:
        """Publish connect/disconnect events and periodic peer counts."""
        engine = self._engine
        while True:
            try:
                current = {
                    str(peer) for peer in engine.host.get_connected_peers()
                }
                previous = self._known_connected_peers
                new_peers = current - previous
                if self._notifications is not None:
                    for peer_id in sorted(new_peers):
                        self._notifications.publish_event(
                            "peer_connected", {"peer_id": peer_id}
                        )
                    for peer_id in sorted(previous - current):
                        self._notifications.publish_event(
                            "peer_disconnected", {"peer_id": peer_id}
                        )
                self._known_connected_peers = current

                if new_peers:
                    chat_room = getattr(engine, "chat_room", None)
                    if chat_room is not None:
                        announce = getattr(chat_room, "announce_profile", None)
                        if announce is not None:
                            try:
                                await announce()
                            except Exception:
                                logger.debug(
                                    "Could not announce profile after peer connect",
                                    exc_info=True,
                                )
                        announce_disc = getattr(
                            chat_room, "announce_discovery", None
                        )
                        if announce_disc is not None:
                            try:
                                await announce_disc()
                            except Exception:
                                logger.debug(
                                    "Could not announce discovery after peer connect",
                                    exc_info=True,
                                )

                logger.debug("Connected peers are: %d", len(current))
                logger.debug(
                    "Peers in peer store are: %d",
                    len(engine.host.get_peerstore().peers_with_addrs()),
                )
                dht = getattr(engine, "dht", None)
                if dht is not None:
                    logger.debug(
                        "Peers in routing table are: %d",
                        len(dht.routing_table.get_peer_ids()),
                    )
                pubsub = getattr(engine, "pubsub", None)
                if pubsub is not None:
                    logger.debug("Peers in pubsub are: %d", len(pubsub.peers.keys()))
            except Exception as e:
                # A status-logging failure must never take down the node.
                logger.warning(f"Peer monitor error: {e}")
            await trio.sleep(5)
