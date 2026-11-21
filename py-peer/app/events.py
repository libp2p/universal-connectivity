"""Framework-independent application events.

Design goals (Phase 2 brief §6.5):
- One event model shared by every adapter.
- Subscribers can subscribe/unsubscribe safely from any thread.
- Publishing never blocks the trio/libp2p thread: queues are bounded and a full
  queue drops the oldest event for that subscriber.
- Consumers may live on a different event loop (Tornado/asyncio) than the
  producer (trio), so each subscription uses a ``janus`` queue.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, cast

import janus
from queue import Full

logger = logging.getLogger("app.events")

DEFAULT_QUEUE_SIZE = 256


class EventType(str, Enum):
    """Application event names.

    Values are stable strings so adapters can filter without importing enums
    into their protocols.
    """

    MESSAGE_RECEIVED = "message_received"
    SYSTEM = "system"
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    TOPIC_SUBSCRIBED = "topic_subscribed"
    MESH_UPDATED = "mesh_updated"
    TRANSPORT_STATUS = "transport_status"


@dataclass(frozen=True)
class Event:
    """Immutable application event."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventSubscription:
    """A single subscriber's bounded queue.

    ``queue.sync_q`` is the thread-safe side consumed by adapters. ``dropped``
    counts events discarded because the consumer was slower than the producer.
    """

    def __init__(self, types: set[EventType] | None, maxsize: int):
        self.types = types
        self.queue: janus.Queue[Event] = janus.Queue(maxsize=maxsize)
        self.dropped = 0
        self._closed = False

    def accepts(self, event_type: EventType) -> bool:
        return self.types is None or event_type in self.types

    def get_nowait(self) -> Event | None:
        """Return the next event, or None when empty/closed."""
        try:
            return self.queue.sync_q.get_nowait()
        except Exception:
            # Empty, or the queue was closed underneath the consumer (janus
            # raises its own ShutDown type, which is not a RuntimeError).
            return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.queue.close()
        except Exception:
            logger.debug("Error closing event subscription queue", exc_info=True)

    @property
    def closed(self) -> bool:
        return self._closed


class EventBus:
    """Thread-safe, bounded, non-blocking fan-out of application events."""

    def __init__(self, maxsize: int = DEFAULT_QUEUE_SIZE):
        self.maxsize = maxsize
        self._subscribers: set[EventSubscription] = set()
        self._lock = threading.RLock()
        self._published = 0

    def subscribe(
        self,
        types: Iterable[EventType | str] | None = None,
        maxsize: int | None = None,
    ) -> EventSubscription:
        """Register a subscriber, optionally filtering by event type."""
        normalized: set[EventType] | None = None
        if types is not None:
            normalized = set()
            for item in types:
                if isinstance(item, EventType):
                    normalized.add(item)
                else:
                    # Pyrefly 0.17 infers enum constructors as ``str``; mypy
                    # already narrows this to EventType.
                    normalized.add(cast(EventType, EventType(item)))  # type: ignore[redundant-cast]
        subscription = EventSubscription(normalized, maxsize or self.maxsize)
        with self._lock:
            self._subscribers.add(subscription)
        return subscription

    def unsubscribe(self, subscription: EventSubscription) -> None:
        """Remove and close a subscription. Safe to call twice."""
        with self._lock:
            self._subscribers.discard(subscription)
        subscription.close()

    def publish(self, event: Event) -> None:
        """Publish without blocking. Never raises to the networking loop."""
        with self._lock:
            subscribers = list(self._subscribers)
            self._published += 1
        for subscription in subscribers:
            if subscription.closed or not subscription.accepts(event.type):
                continue
            try:
                subscription.queue.sync_q.put_nowait(event)
            except Full:
                # Slow consumer: drop the oldest queued event and retry once.
                try:
                    subscription.queue.sync_q.get_nowait()
                    subscription.dropped += 1
                    subscription.queue.sync_q.put_nowait(event)
                except Exception:
                    subscription.dropped += 1
            except Exception:
                # Queue closed between snapshot and write.
                continue

    def close(self) -> None:
        """Close every subscription (runtime shutdown)."""
        with self._lock:
            subscribers = list(self._subscribers)
            self._subscribers.clear()
        for subscription in subscribers:
            subscription.close()

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @property
    def published_count(self) -> int:
        return self._published
