"""
WebSocket handlers — real-time streaming for API clients.

WS /ws/messages   - stream chat + file messages from message_queue
WS /ws/system     - stream system events from system_queue
WS /ws/peers      - periodic peer list updates
WS /ws/pubsub/mesh - periodic GossipSub mesh topology updates
"""

import json
import time
import logging
import asyncio

import tornado.websocket

logger = logging.getLogger("api.websocket")

# How often (seconds) periodic pushes fire for peers and mesh endpoints
PEERS_PUSH_INTERVAL = 3.0
MESH_PUSH_INTERVAL  = 5.0


class BaseWebSocketHandler(tornado.websocket.WebSocketHandler):
    """Shared WebSocket base: CORS + injected service."""

    def initialize(self, service):
        self.service = service
        self._running = False
        self._task: asyncio.Task | None = None

    def check_origin(self, origin):
        return True  # Allow all origins (CORS)

    def open(self):
        self._running = True
        logger.info(f"WS opened: {self.__class__.__name__}")
        self._task = asyncio.get_event_loop().create_task(self._push_loop())

    def on_close(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info(f"WS closed: {self.__class__.__name__}")

    def on_message(self, message):
        """Sub-classes override this to handle client commands."""
        pass

    async def _push_loop(self):
        """Override in subclass."""
        pass

    def _safe_write(self, data: dict):
        try:
            self.write_message(json.dumps(data))
        except tornado.websocket.WebSocketClosedError:
            self._running = False


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

    def initialize(self, service):
        super().initialize(service)
        self._topic_filter: str | None = None

    def on_message(self, raw):
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

    async def _push_loop(self):
        # Wait until service is ready
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        mq = self.service.get_message_queue()
        if not mq:
            return

        while self._running:
            try:
                # Drain all available messages
                while True:
                    try:
                        msg = mq.sync_q.get_nowait()
                        # Apply optional topic filter
                        if self._topic_filter and msg.get("topic") != self._topic_filter:
                            continue
                        self._safe_write({"event": msg.get("type", "message"), "data": msg})
                    except Exception:
                        break
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

    async def _push_loop(self):
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        sq = self.service.get_system_queue()
        if not sq:
            return

        while self._running:
            try:
                while True:
                    try:
                        msg = sq.sync_q.get_nowait()
                        self._safe_write({"event": "system_message", "data": msg})
                    except Exception:
                        break
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

    async def _push_loop(self):
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        last_peers: list = []
        while self._running:
            try:
                info = self.service.get_connection_info()
                peers = sorted(str(p) for p in info.get("connected_peers", set()))
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

    async def _push_loop(self):
        while self._running and not (self.service and self.service.ready):
            await asyncio.sleep(0.2)

        while self._running:
            try:
                raw_mesh = getattr(self.service.gossipsub, "mesh", {})
                mesh = {
                    topic: sorted(str(p) for p in peers)
                    for topic, peers in raw_mesh.items()
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
