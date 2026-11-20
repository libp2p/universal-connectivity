"""Durable application storage.

Phase 3 adds a message repository with stable identity, dedupe, and bounded
per-topic retention, backed by either process memory (default) or a local
SQLite file. ``open_store(path)`` is the only entry point; the rest of the
application depends on the repository interface, not on SQLite.

There is no server database and no offline delivery: storage is local
retention of messages the peer already observed.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from typing import Any

from ..errors import StorageError
from .messages import (
    DEFAULT_RETENTION,
    MAX_HISTORY_LIMIT,
    MAX_RETENTION,
    InMemoryMessageStore,
    SqliteMessageStore,
    message_identity,
    normalize_message,
)
from .repositories import (
    MemoryPeerRepository,
    MemorySettingsRepository,
    SqlitePeerRepository,
    SqliteSettingsRepository,
)
from .schema import SCHEMA_VERSION, migrate

__all__ = [
    "DEFAULT_RETENTION",
    "MAX_HISTORY_LIMIT",
    "MAX_RETENTION",
    "SCHEMA_VERSION",
    "MemoryStore",
    "SqliteStore",
    "InMemoryMessageStore",
    "SqliteMessageStore",
    "message_identity",
    "normalize_message",
    "open_store",
]

logger = logging.getLogger("app.storage")


class MemoryStore:
    """Ephemeral store: same interface as the durable one, no files.

    The store is the facade the rest of the application talks to; ``messages``
    remains available for repository-level use and tests.
    """

    backend = "memory"
    durable = False

    def __init__(self, retention: int = DEFAULT_RETENTION) -> None:
        self.messages = InMemoryMessageStore(retention)
        self.peers = MemoryPeerRepository()
        self.settings = MemorySettingsRepository()
        self.schema_version = None

    @property
    def retention(self) -> int:
        return self.messages.retention

    # --- message repository delegation --------------------------------
    def append(self, message: dict[str, Any], keep: int | None = None) -> bool:
        return self.messages.append(message, keep=keep)

    def page(
        self, topic: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        return self.messages.page(topic, limit=limit, offset=offset)

    def unread_count(self, topic: str) -> int:
        return self.messages.unread_count(topic)

    def mark_read(self, topic: str) -> int:
        return self.messages.mark_read(topic)

    def stats(self, topic: str) -> dict[str, Any]:
        return self.messages.stats(topic)

    def count(self) -> int:
        return self.messages.count()

    def close(self) -> None:
        self.messages.close()

    def health(self) -> dict[str, Any]:
        return {
            **self.messages.health(),
            "peer_records": self.peers.count(),
            "settings": len(self.settings.all()),
        }


class SqliteStore:
    """Durable store backed by one local SQLite file.

    One connection is shared behind a lock: the trio thread writes, the Tornado
    thread reads, and WAL keeps readers from blocking the writer. The runtime
    performs durable appends on a worker thread so disk latency never stalls
    the networking loop.
    """

    backend = "sqlite"
    durable = True

    def __init__(self, path: str, retention: int = DEFAULT_RETENTION) -> None:
        self.path = os.fspath(path)
        self._lock = threading.RLock()
        self._closed = False

        directory = os.path.dirname(os.path.abspath(self.path))
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as exc:
                raise StorageError(
                    f"Could not create the storage directory '{directory}': {exc}"
                ) from exc

        try:
            connection = sqlite3.connect(
                self.path, timeout=5.0, check_same_thread=False
            )
        except sqlite3.Error as exc:
            raise StorageError(f"Could not open the storage database: {exc}") from exc

        connection.row_factory = sqlite3.Row
        self._connection = connection
        try:
            with self._lock:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = NORMAL")
                connection.execute("PRAGMA busy_timeout = 5000")
            self.schema_version = migrate(connection)
        except StorageError:
            connection.close()
            raise
        except sqlite3.Error as exc:
            connection.close()
            raise StorageError(f"Storage migration failed: {exc}") from exc

        self.messages = SqliteMessageStore(connection, self._lock, retention)
        self.peers = SqlitePeerRepository(connection, self._lock)
        self.settings = SqliteSettingsRepository(connection, self._lock)

    @property
    def retention(self) -> int:
        return self.messages.retention

    # --- message repository delegation --------------------------------
    def append(self, message: dict[str, Any], keep: int | None = None) -> bool:
        return self.messages.append(message, keep=keep)

    def page(
        self, topic: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        return self.messages.page(topic, limit=limit, offset=offset)

    def unread_count(self, topic: str) -> int:
        return self.messages.unread_count(topic)

    def mark_read(self, topic: str) -> int:
        return self.messages.mark_read(topic)

    def stats(self, topic: str) -> dict[str, Any]:
        return self.messages.stats(topic)

    def count(self) -> int:
        return self.messages.count()

    def close(self) -> None:
        """Close the connection. Safe to call more than once."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._connection.close()
            except sqlite3.Error:  # pragma: no cover - shutdown race
                logger.debug("Storage connection close failed", exc_info=True)

    def health(self) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                return {
                    "backend": self.backend,
                    "durable": True,
                    "schema_version": self.schema_version,
                    "closed": True,
                }
        return {
            **self.messages.health(),
            "schema_version": self.schema_version,
            "peer_records": self.peers.count(),
            "settings": len(self.settings.all()),
        }


def open_store(
    path: str | None = None, retention: int = DEFAULT_RETENTION
) -> MemoryStore | SqliteStore:
    """Return a durable store when ``path`` is given, else an in-memory one."""
    if path:
        return SqliteStore(path, retention=retention)
    return MemoryStore(retention)
