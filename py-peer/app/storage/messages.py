"""Message repository: stable identity, dedupe, and per-topic retention.

Both backends expose the same narrow interface so the networking engine and the
storage service never know which one they are talking to::

    append(message, keep=None) -> bool    # False when the id was stored already
    page(topic, limit, offset) -> (messages, total)
    unread_count(topic) / mark_read(topic) / stats(topic)
    count() / health() / close()

Delivery semantics are unchanged: this is local retention of messages observed
on a subscribed topic. It is not an offline mailbox, an acknowledgement, or a
network-wide delivery guarantee.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from typing import Any

from ..errors import StorageError, ValidationError

DEFAULT_RETENTION = 1000
MAX_RETENTION = 100_000
MAX_HISTORY_LIMIT = 1000


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def message_identity(message: dict[str, Any]) -> str:
    """Return the stable identity of a chat message.

    Identity is ``(topic, sender, timestamp, content)``. GossipSub may deliver
    the same frame more than once and both copies must collapse into one row.
    Two identical texts sent at different times stay distinct. A caller that
    already has a wire-level id can pass ``message_id`` and it is preserved.
    """
    explicit = message.get("message_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    material = "\x00".join(
        [
            str(message.get("topic") or "default"),
            str(message.get("sender_id") or ""),
            f"{_as_float(message.get('timestamp'), 0.0):.6f}",
            str(message.get("message") or ""),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Coerce a network/UI message into the stored shape.

    Network input is untrusted, so unknown keys are dropped and scalar fields
    are coerced instead of raising. The repository, not the engine, owns this
    shape and the message id.
    """
    if not isinstance(message, dict):
        raise StorageError("A chat message must be a mapping.")
    topic = message.get("topic") or "default"
    if not isinstance(topic, str) or not topic.strip():
        raise ValidationError("Message topic must be a non-empty string.")
    data = {
        "message_id": message_identity(message),
        "type": str(message.get("type") or "chat_message"),
        "message": str(message.get("message") or ""),
        "sender_nick": str(message.get("sender_nick") or "unknown"),
        "sender_id": str(message.get("sender_id") or ""),
        "timestamp": _as_float(message.get("timestamp"), time.time()),
        "topic": topic.strip(),
        "read": bool(message.get("read", False)),
    }
    for key in ("file_cid", "file_name"):
        if message.get(key) is not None:
            data[key] = str(message[key])
    if message.get("file_size") is not None:
        try:
            data["file_size"] = int(message["file_size"])
        except (TypeError, ValueError):
            pass
    return data


def _check_retention(keep: int) -> int:
    if not isinstance(keep, int) or isinstance(keep, bool) or not 1 <= keep <= MAX_RETENTION:
        raise ValidationError(
            f"Retention must be between 1 and {MAX_RETENTION} messages per topic."
        )
    return keep


def _check_page(limit: int, offset: int) -> tuple[int, int]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_HISTORY_LIMIT:
        raise ValidationError(
            f"'limit' must be between 1 and {MAX_HISTORY_LIMIT}."
        )
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValidationError("'offset' must be zero or greater.")
    return limit, offset


class InMemoryMessageStore:
    """Default backend: bounded per-topic history in this process only."""

    backend = "memory"
    durable = False

    def __init__(self, retention: int = DEFAULT_RETENTION):
        self.retention = _check_retention(retention)
        self._lock = threading.RLock()
        self._by_topic: dict[str, list[dict[str, Any]]] = {}
        self._seen: set[str] = set()
        self._unread: dict[str, int] = {}

    def append(self, message: dict[str, Any], keep: int | None = None) -> bool:
        data = normalize_message(message)
        limit = _check_retention(keep if keep is not None else self.retention)
        topic = data["topic"]
        with self._lock:
            if data["message_id"] in self._seen:
                return False
            messages = self._by_topic.setdefault(topic, [])
            messages.append(data)
            self._seen.add(data["message_id"])
            if not data["read"]:
                self._unread[topic] = self._unread.get(topic, 0) + 1

            overflow = len(messages) - limit
            if overflow > 0:
                removed = messages[:overflow]
                del messages[:overflow]
                for old in removed:
                    self._seen.discard(old["message_id"])
                    if not old.get("read", False):
                        self._unread[topic] = max(0, self._unread.get(topic, 0) - 1)
            return True

    def page(
        self, topic: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _check_page(limit, offset)
        with self._lock:
            messages = self._by_topic.get(topic, [])
            total = len(messages)
            # Copy every row: callers serialise on another thread while the
            # engine may still be appending or flipping read flags.
            return [dict(message) for message in messages[offset: offset + limit]], total

    def unread_count(self, topic: str) -> int:
        with self._lock:
            return self._unread.get(topic, 0)

    def mark_read(self, topic: str) -> int:
        with self._lock:
            marked = 0
            for message in self._by_topic.get(topic, []):
                if not message.get("read", False):
                    message["read"] = True
                    marked += 1
            self._unread[topic] = 0
            return marked

    def stats(self, topic: str) -> dict[str, Any]:
        with self._lock:
            messages = self._by_topic.get(topic, [])
            return {
                "unread_count": self._unread.get(topic, 0),
                "total_count": len(messages),
                "last_message": dict(messages[-1]) if messages else None,
            }

    def count(self) -> int:
        with self._lock:
            return sum(len(messages) for messages in self._by_topic.values())

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "durable": self.durable,
            "schema_version": None,
            "retention_per_topic": self.retention,
            "messages": self.count(),
        }

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass


def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    data = {
        "message_id": row["id"],
        "type": row["kind"],
        "message": row["content"],
        "sender_nick": row["sender_nick"],
        "sender_id": row["sender_id"],
        "timestamp": row["timestamp"],
        "topic": row["topic"],
        "read": bool(row["read"]),
    }
    for key in ("file_cid", "file_name", "file_size"):
        if row[key] is not None:
            data[key] = row[key]
    return data


class SqliteMessageStore:
    """Durable backend sharing one serialised SQLite connection.

    Writes are tiny (one INSERT plus one retention DELETE in a single
    transaction) and the shared lock keeps the Tornado reader thread consistent
    with the trio writer. The engine can run ``append`` on a worker thread via
    ``trio.to_thread`` so a slow disk never stalls the networking loop.
    """

    backend = "sqlite"
    durable = True

    def __init__(self, connection: sqlite3.Connection, lock: threading.RLock,
                 retention: int = DEFAULT_RETENTION):
        self.retention = _check_retention(retention)
        self._connection = connection
        self._lock = lock

    def append(self, message: dict[str, Any], keep: int | None = None) -> bool:
        data = normalize_message(message)
        limit = _check_retention(keep if keep is not None else self.retention)
        topic = data["topic"]
        try:
            with self._lock, self._connection:
                cursor = self._connection.execute(
                    """
                    INSERT OR IGNORE INTO messages
                        (id, topic, sender_id, sender_nick, content, kind,
                         timestamp, received_at, read, file_cid, file_name,
                         file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["message_id"],
                        topic,
                        data["sender_id"],
                        data["sender_nick"],
                        data["message"],
                        data["type"],
                        data["timestamp"],
                        time.time(),
                        1 if data["read"] else 0,
                        data.get("file_cid"),
                        data.get("file_name"),
                        data.get("file_size"),
                    ),
                )
                if cursor.rowcount == 0:
                    return False
                # Retention is enforced in the same transaction as the insert,
                # so unread counts (computed from rows) stay consistent.
                self._connection.execute(
                    """
                    DELETE FROM messages
                    WHERE topic = ?
                      AND id NOT IN (
                          SELECT id FROM messages
                          WHERE topic = ?
                          ORDER BY rowid DESC
                          LIMIT ?
                      )
                    """,
                    (topic, topic, limit),
                )
                return True
        except sqlite3.Error as exc:
            raise StorageError(f"Could not store message: {exc}") from exc

    def page(
        self, topic: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _check_page(limit, offset)
        try:
            with self._lock:
                total = self._connection.execute(
                    "SELECT COUNT(*) FROM messages WHERE topic = ?", (topic,)
                ).fetchone()[0]
                rows = self._connection.execute(
                    """
                    SELECT * FROM messages
                    WHERE topic = ?
                    ORDER BY rowid ASC
                    LIMIT ? OFFSET ?
                    """,
                    (topic, limit, offset),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read message history: {exc}") from exc
        return [_row_to_message(row) for row in rows], total

    def unread_count(self, topic: str) -> int:
        try:
            with self._lock:
                return self._connection.execute(
                    "SELECT COUNT(*) FROM messages WHERE topic = ? AND read = 0",
                    (topic,),
                ).fetchone()[0]
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read unread count: {exc}") from exc

    def mark_read(self, topic: str) -> int:
        try:
            with self._lock, self._connection:
                cursor = self._connection.execute(
                    "UPDATE messages SET read = 1 WHERE topic = ? AND read = 0",
                    (topic,),
                )
                return cursor.rowcount
        except sqlite3.Error as exc:
            raise StorageError(f"Could not mark messages as read: {exc}") from exc

    def stats(self, topic: str) -> dict[str, Any]:
        try:
            with self._lock:
                total = self._connection.execute(
                    "SELECT COUNT(*) FROM messages WHERE topic = ?", (topic,)
                ).fetchone()[0]
                unread = self._connection.execute(
                    "SELECT COUNT(*) FROM messages WHERE topic = ? AND read = 0",
                    (topic,),
                ).fetchone()[0]
                last = self._connection.execute(
                    "SELECT * FROM messages WHERE topic = ? ORDER BY rowid DESC LIMIT 1",
                    (topic,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read topic stats: {exc}") from exc
        return {
            "unread_count": unread,
            "total_count": total,
            "last_message": _row_to_message(last) if last is not None else None,
        }

    def count(self) -> int:
        try:
            with self._lock:
                return self._connection.execute(
                    "SELECT COUNT(*) FROM messages"
                ).fetchone()[0]
        except sqlite3.Error as exc:
            raise StorageError(f"Could not count messages: {exc}") from exc

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "durable": self.durable,
            "retention_per_topic": self.retention,
            "messages": self.count(),
        }

    def close(self) -> None:  # pragma: no cover - the store owns the connection
        pass
