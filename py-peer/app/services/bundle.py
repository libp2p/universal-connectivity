"""Service composition root.

``ServiceBundle`` wires the services around one engine (transport owner) and
starts the trio workers that previously lived in ``HeadlessService``. The
engine holds transport primitives only; application behaviour lives here.
"""

from __future__ import annotations

from typing import Any

from .addressing import AddressService
from .connection import ConnectionService
from .discovery import DiscoveryService
from .files import FileService
from .identity import IdentityService
from .messaging import MessagingService
from .notifications import NotificationService
from .peer import PeerService
from .storage import StorageService
from ..storage import MemoryStore


class ServiceBundle:
    """One instance of every application service for a single engine."""

    def __init__(
        self, engine: Any, store: Any = None, event_bus: Any = None
    ) -> None:
        self.engine = engine
        if event_bus is not None:
            engine.event_bus = event_bus

        self.notifications = NotificationService(engine)
        self.addresses = AddressService(engine)
        self.identity = IdentityService(engine)
        self.storage = StorageService(
            engine,
            store or getattr(engine, "message_store", None) or MemoryStore(),
            notifications=self.notifications,
        )
        self.messaging = MessagingService(
            engine,
            self.storage,
            notifications=self.notifications,
            identity=self.identity,
        )
        self.connections = ConnectionService(
            engine,
            addresses=self.addresses,
            notifications=self.notifications,
        )
        self.discovery = DiscoveryService(
            engine,
            storage=self.storage,
            messaging=self.messaging,
            notifications=self.notifications,
            connections=self.connections,
        )
        self.files = FileService(engine, notifications=self.notifications)
        self.peers = PeerService(engine, notifications=self.notifications)

    # ------------------------------------------------------------------ #
    #  Wiring
    # ------------------------------------------------------------------ #
    def bind_store(self, store: Any) -> None:
        """Point storage at a store injected after construction."""
        self.storage.bind_store(store)

    async def setup(self) -> None:
        """Join the chat room before the transport starts dialing peers."""
        await self.messaging.setup_chat_room()

    async def shutdown(self) -> None:
        """Stop services that own runtime resources."""
        await self.messaging.stop_chat_room()
        self.notifications.close()

    def start_workers(self, nursery: Any) -> None:
        """Start every long-running service loop in the engine's nursery."""
        nursery.start_soon(self.messaging.process_incoming)
        nursery.start_soon(self.messaging.process_outgoing)
        nursery.start_soon(self.discovery.process_topic_subscriptions)
        nursery.start_soon(self.discovery.run_dht_discovery)
        nursery.start_soon(self.connections.process_peer_connections)
        nursery.start_soon(self.files.process_file_shares)
        nursery.start_soon(self.files.process_file_downloads)
        nursery.start_soon(self.peers.monitor_peers)


__all__ = ["ServiceBundle"]
