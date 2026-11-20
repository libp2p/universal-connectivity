"""Message retention and stored-message queries.

The repository owns identity, dedupe, and retention. This service is the
application-facing boundary: it assigns the stable message id, keeps durable
writes off the networking loop, and produces the topic views adapters use.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

import trio

from ..constants import MAX_TOPIC_MESSAGES
from ..errors import ValidationError
from ..storage import MAX_HISTORY_LIMIT, message_identity

logger = logging.getLogger("app.services.storage")


class StorageService:
    """Read/write view of retained application data."""

    def __init__(
        self, engine: Any, store: Any = None, notifications: Any = None
    ) -> None:
        self._engine = engine
        self._notifications = notifications
        self._store: Any = store
        if self._store is None:
            self._store = getattr(engine, "message_store", None)
        if self._store is None:
            raise ValueError(
                "StorageService requires a message store "
                "(pass store= or set engine.message_store)"
            )

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def store(self) -> Any:
        return self._store

    @property
    def backend(self) -> str:
        return self._store.backend

    @property
    def durable(self) -> bool:
        return bool(getattr(self._store, "durable", False))

    def bind_store(self, store: Any) -> None:
        """Replace the backing store (used when a runtime injects one)."""
        self._store = store
        self._engine.message_store = store

    # ------------------------------------------------------------------ #
    #  Writes
    # ------------------------------------------------------------------ #
    async def append_message(self, message_data: dict[str, Any]) -> bool:
        """Persist a message, keeping slow disk I/O off the networking loop.

        Durable stores run the repository call on a worker thread. A storage
        failure must not take down the node or hide a live message, so it is
        reported as a system message and delivery continues.
        """
        # Give the message its stable id before it reaches the repository, so
        # the stored row and the payload sent to UI/API agree. The repository
        # rejects an id it already holds: GossipSub can deliver the same frame
        # twice (including our own echo), and showing it twice is the bug this
        # dedupe exists to prevent.
        message_data.setdefault("message_id", message_identity(message_data))
        store = self._store
        try:
            if getattr(store, "durable", False):
                return await trio.to_thread.run_sync(
                    functools.partial(
                        store.append, message_data, keep=MAX_TOPIC_MESSAGES
                    )
                )
            return store.append(message_data, keep=MAX_TOPIC_MESSAGES)
        except Exception as exc:
            logger.error(f"Failed to store chat message: {exc}")
            if self._notifications is not None:
                await self._notifications.system(
                    "Failed to persist a chat message."
                )
            return True

    # ------------------------------------------------------------------ #
    #  Reads
    # ------------------------------------------------------------------ #
    def history(
        self, topic: str, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """Return a paginated slice of retained topic history."""
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_HISTORY_LIMIT
        ):
            raise ValidationError(
                f"'limit' must be between 1 and {MAX_HISTORY_LIMIT}."
            )
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValidationError("'offset' must be zero or greater.")
        messages, total = self._store.page(topic, limit=limit, offset=offset)
        return {
            "topic": topic,
            "messages": messages,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def topic_messages(self, topic: str) -> list[dict[str, Any]]:
        """Return one topic's retained messages (bounded snapshot)."""
        messages, _total = self._store.page(
            topic, limit=min(MAX_TOPIC_MESSAGES, 1000), offset=0
        )
        return messages

    def topics(self) -> dict[str, Any]:
        """Return stats for every subscribed topic."""
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is None:
            topics: set[str] = set()
        else:
            topics = set(chat_room.get_subscribed_topics())
        return {topic: self._store.stats(topic) for topic in topics}

    def unread(self, topic: str) -> int:
        return self._store.unread_count(topic)

    def mark_read(self, topic: str) -> None:
        marked = self._store.mark_read(topic)
        if marked:
            logger.debug(f"Marked {marked} messages in topic '{topic}' as read")

    def health(self) -> dict[str, Any]:
        return self._store.health()
