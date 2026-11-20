"""Outbound notifications and per-client fan-out.

This service owns everything the engine used to do around the legacy UI
queues: system messages, per-WebSocket-client subscriber queues, and
application-event publication. Producers are the trio/libp2p thread; consumers
live on Tornado/asyncio threads, so every write is non-blocking.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, cast

import janus

from ..events import Event, EventType

logger = logging.getLogger("app.services.notifications")


class NotificationService:
    """Publish messages, system notices, and application events."""

    def __init__(self, engine: Any):
        self._engine = engine
        self._message_subscribers: set[janus.Queue[dict[str, Any]]] = set()
        self._system_subscribers: set[janus.Queue[dict[str, Any]]] = set()
        self._subscribers_lock = threading.RLock()

    # ------------------------------------------------------------------ #
    #  Application events
    # ------------------------------------------------------------------ #
    def publish_event(self, event_type: Any, data: dict[str, Any]) -> None:
        """Publish to the runtime event bus without ever blocking.

        Imported lazily through ``app.events``; failures must not affect
        delivery.
        """
        bus = getattr(self._engine, "event_bus", None)
        if bus is None:
            return
        try:
            try:
                # Pyrefly 0.17 infers enum constructors as ``str``; mypy
                # already narrows this to EventType.
                typed_event = cast(EventType, EventType(event_type))  # type: ignore[redundant-cast]
            except (TypeError, ValueError):
                logger.warning("Unknown event type %r", event_type)
                return
            bus.publish(Event(typed_event, dict(data)))
        except Exception:
            logger.debug("Failed to publish %s event", event_type, exc_info=True)

    # ------------------------------------------------------------------ #
    #  Fan-out to legacy queues and WebSocket subscribers
    # ------------------------------------------------------------------ #
    @staticmethod
    def put_legacy(queue: Any, payload: dict[str, Any]) -> None:
        """Best-effort write to a bounded legacy UI queue.

        A legacy queue is optional (API/headless deployments have no consumer),
        so a full or closed queue must never block the trio thread or raise.
        """
        if queue is None:
            return
        try:
            queue.sync_q.put_nowait(payload)
        except Exception:
            pass

    def _fanout(
        self,
        subscribers: set[janus.Queue[dict[str, Any]]],
        payload: dict[str, Any],
    ) -> None:
        """Copy an event to every registered subscriber (non-blocking)."""
        # Snapshot under the lock: WebSocket open/close happens on the Tornado
        # thread while fan-out runs on the trio thread. Iterating the live set
        # can raise "Set changed size during iteration" and drop the event.
        with self._subscribers_lock:
            snapshot = list(subscribers)
        for queue in snapshot:
            try:
                queue.sync_q.put_nowait(payload)
            except Exception:
                # Queue full (slow client) or closed — drop this client's copy.
                pass

    def message(self, payload: dict[str, Any]) -> None:
        """Deliver a chat/file payload to the legacy queue and subscribers."""
        self.put_legacy(getattr(self._engine, "message_queue", None), payload)
        self._fanout(self._message_subscribers, payload)

    def system_payload(self, payload: dict[str, Any]) -> None:
        """Deliver a system payload to the legacy queue and subscribers."""
        self.put_legacy(getattr(self._engine, "system_queue", None), payload)
        self._fanout(self._system_subscribers, payload)

    async def system(self, message: str) -> None:
        """Publish a human-readable system message."""
        logger.debug("system message: %s", message)
        try:
            self.publish_event(
                "system",
                {
                    "type": "system_message",
                    "message": message,
                    "timestamp": time.time(),
                },
            )
            if getattr(self._engine, "system_queue", None) is not None:
                self.system_payload(
                    {
                        "type": "system_message",
                        "message": message,
                        "timestamp": time.time(),
                    }
                )
            else:
                logger.warning(
                    "System queue not available, cannot send message: %s", message
                )
        except Exception:
            logger.exception("Error sending system message")

    def register_subscriber(
        self, kind: str = "message"
    ) -> janus.Queue[dict[str, Any]]:
        """Register a per-WebSocket-client queue that receives every event."""
        subscribers = (
            self._message_subscribers if kind == "message" else self._system_subscribers
        )
        queue: janus.Queue[dict[str, Any]] = janus.Queue(maxsize=256)
        with self._subscribers_lock:
            subscribers.add(queue)
        return queue

    def unsubscribe(self, kind: str, queue: janus.Queue[dict[str, Any]]) -> None:
        """Remove and close a previously registered subscriber queue."""
        subscribers = (
            self._message_subscribers if kind == "message" else self._system_subscribers
        )
        with self._subscribers_lock:
            subscribers.discard(queue)
        try:
            queue.close()
        except Exception:
            pass

    def close(self) -> None:
        """Close every per-client queue (runtime shutdown)."""
        with self._subscribers_lock:
            queues = list(self._message_subscribers | self._system_subscribers)
            self._message_subscribers.clear()
            self._system_subscribers.clear()
        for queue in queues:
            try:
                queue.close()
            except Exception:
                pass
