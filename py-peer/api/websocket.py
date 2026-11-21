"""
WebSocket handlers — real-time streaming for API clients.

WS /ws/messages   - stream chat + file messages (application event bus)
WS /ws/system     - stream system events (application event bus)
WS /ws/peers      - periodic peer list updates
WS /ws/pubsub/mesh - periodic GossipSub mesh topology updates

Message and system streams subscribe to the runtime's bounded event bus: a
slow browser can only fill its own queue, and the producer (the trio/libp2p
thread) never blocks. Engines without an event bus (legacy embedders) fall
back to the per-client legacy queue.
"""

import json
import time
import logging
import asyncio
from queue import Empty
from typing import Any

import tornado.websocket

logger = logging.getLogger("api.websocket")

# How often (seconds) periodic pushes fire for peers and mesh endpoints
PEERS_PUSH_INTERVAL = 3.0
MESH_PUSH_INTERVAL  = 5.0


class BaseWebSocketHandler(tornado.websocket.WebSocketHandler):
    """Shared WebSocket base: CORS + injected shared runtime."""

    runtime: Any
    service: Any
    _running: bool
    _task: asyncio.Task[None] | None

    def initialize(self, runtime: Any) -> None:
        from .base import as_runtime

        self.runtime = as_runtime(runtime)
        self.service = self.runtime.service
        self._running = False
        self._task = None

    def check_origin(self, origin: str) -> bool:
        return True  # Allow all origins (CORS)

    def open(self, *args: str, **kwargs: str) -> None:
        self._running = True
        logger.info(f"WS opened: {self.__class__.__name__}")
        self._task = asyncio.create_task(self._push_loop())

    def on_close(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info(f"WS closed: {self.__class__.__name__}")

    def on_message(self, message: str | bytes) -> None:
        """Sub-classes override this to handle client commands."""
        pass

    async def _push_loop(self) -> None:
        """Override in subclass."""
        pass

    def _safe_write(self, data: dict[str, Any]) -> None:
        try:
            self.write_message(json.dumps(data))
        except tornado.websocket.WebSocketClosedError:
            self._running = False

    def _subscribe_events(self, event_types: list[Any]) -> Any:
        """Subscribe to the runtime event bus, or return None if unavailable."""
        events = getattr(self.runtime, "events", None)
        if events is None:
            return None
        return self.runtime.subscribe(event_types)


# ──────────────────────────────────────────────────────────
#  WS /ws/messages
# ──────────────────────────────────────────────────────────
class MessageStreamHandler(BaseWebSocketHandler):
    """
    Streams all incoming chat and file messages in real-time.

    Client can optionally send a JSON command to filter by topic:
        { "action": "filter_topic", "topic": "my-channel" }
        { "action": "unfilter" }
    """

    _topic_filter: str | None
    _subscription: Any
    _legacy_queue: Any

    def initialize(self, runtime: Any) -> None:
        super().initialize(runtime)
        self._topic_filter = None
        self._subscription = None
        self._legacy_queue = None

    def open(self, *args: str, **kwargs: str) -> None:
        from app.events import EventType

        # Every subscriber gets its own bounded queue: multiple tabs all see
        # every message instead of stealing from a single-consumer queue.
        self._subscription = self._subscribe_events([EventType.MESSAGE_RECEIVED])
        if self._subscription is None and self.service:
            self._legacy_queue = self.service.register_subscriber("message")
        super().open()

    def on_close(self) -> None:
        super().on_close()
        if self._subscription is not None:
            self.runtime.unsubscribe(self._subscription)
            self._subscription = None
        if self._legacy_queue is not None and self.service:
            self.service.unregister_subscriber("message", self._legacy_queue)
            self._legacy_queue = None

    def on_message(self, raw: str | bytes) -> None:
        try:
            cmd = json.loads(raw)
            action = cmd.get("action")
            if action == "filter_topic":
                self._topic_filter = cmd.get("topic")
                self._safe_write({"event": "filter_set", "topic": self._topic_filter})
            elif action == "unfilter":
                self._topic_filter = None
                self._safe_write({"event": "filter_cleared"})
        except Exception:
            pass

    async def _push_loop(self) -> None:
        # Wait until service is ready
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        legacy_queue = self._legacy_queue
        if self._subscription is None and legacy_queue is None:
            return

        while self._running:
            try:
                while True:
                    if self._subscription is not None:
                        event = self._subscription.get_nowait()
                        msg = None if event is None else event.data
                    elif legacy_queue is not None:
                        try:
                            msg = legacy_queue.sync_q.get_nowait()
                        except Empty:
                            msg = None
                    else:
                        break
                    if msg is None:
                        break
                    if self._topic_filter and msg.get("topic") != self._topic_filter:
                        continue
                    self._safe_write({"event": msg.get("type", "message"), "data": msg})
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MessageStreamHandler error: {e}")
                await asyncio.sleep(1)


# ──────────────────────────────────────────────────────────
#  WS /ws/system
# ──────────────────────────────────────────────────────────
class SystemStreamHandler(BaseWebSocketHandler):
    """Streams system events and service notifications."""

    _subscription: Any
    _legacy_queue: Any

    def initialize(self, runtime: Any) -> None:
        super().initialize(runtime)
        self._subscription = None
        self._legacy_queue = None

    def open(self, *args: str, **kwargs: str) -> None:
        from app.events import EventType

        self._subscription = self._subscribe_events([EventType.SYSTEM])
        if self._subscription is None and self.service:
            self._legacy_queue = self.service.register_subscriber("system")
        super().open()

    def on_close(self) -> None:
        super().on_close()
        if self._subscription is not None:
            self.runtime.unsubscribe(self._subscription)
            self._subscription = None
        if self._legacy_queue is not None and self.service:
            self.service.unregister_subscriber("system", self._legacy_queue)
            self._legacy_queue = None

    async def _push_loop(self) -> None:
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        legacy_queue = self._legacy_queue
        if self._subscription is None and legacy_queue is None:
            return

        while self._running:
            try:
                while True:
                    if self._subscription is not None:
                        event = self._subscription.get_nowait()
                        payload = None if event is None else event.data
                    elif legacy_queue is not None:
                        try:
                            payload = legacy_queue.sync_q.get_nowait()
                        except Empty:
                            payload = None
                    else:
                        break
                    if payload is None:
                        break
                    self._safe_write({"event": "system_message", "data": payload})
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SystemStreamHandler error: {e}")
                await asyncio.sleep(1)


# ──────────────────────────────────────────────────────────
#  WS /ws/peers
# ──────────────────────────────────────────────────────────
class PeerUpdateHandler(BaseWebSocketHandler):
    """Pushes the current connected-peer list every PEERS_PUSH_INTERVAL seconds."""

    async def _push_loop(self) -> None:
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        last_peers: list[str] = []
        while self._running:
            try:
                peers = self.runtime.peer.connected_peers()
                if peers != last_peers:
                    last_peers = peers
                    self._safe_write({
                        "event": "peer_update",
                        "data": {
                            "connected_peers": peers,
                            "peer_count": len(peers),
                            "timestamp": time.time(),
                        },
                    })
                await asyncio.sleep(PEERS_PUSH_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"PeerUpdateHandler error: {e}")
                await asyncio.sleep(PEERS_PUSH_INTERVAL)


# ──────────────────────────────────────────────────────────
#  WS /ws/pubsub/mesh
# ──────────────────────────────────────────────────────────
class MeshUpdateHandler(BaseWebSocketHandler):
    """Pushes GossipSub mesh topology every MESH_PUSH_INTERVAL seconds."""

    async def _push_loop(self) -> None:
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        while self._running:
            try:
                mesh = {
                    topic: sorted(peers)
                    for topic, peers in self.runtime.discovery.mesh().items()
                }
                self._safe_write({
                    "event": "mesh_update",
                    "data": {
                        "mesh": mesh,
                        "topic_count": len(mesh),
                        "total_mesh_peers": sum(len(v) for v in mesh.values()),
                        "timestamp": time.time(),
                    },
                })
                await asyncio.sleep(MESH_PUSH_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MeshUpdateHandler error: {e}")
                await asyncio.sleep(MESH_PUSH_INTERVAL)
