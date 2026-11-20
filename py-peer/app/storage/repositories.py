"""Peer metadata and settings repositories.

Schema v1 defines these alongside messages so the storage design is complete:
messages are wired into the runtime now, while identity persistence and user
preferences consume the peer/settings repositories in Phase 4. Keeping them
behind this interface means Phase 4 does not need a second migration design.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Iterable

from ..errors import StorageError, ValidationError

MAX_PAGE = 500


def _check_peer_id(peer_id: str) -> str:
    if not isinstance(peer_id, str) or not peer_id.strip():
        raise ValidationError("Peer ID is required.")
    return peer_id.strip()


def _check_page(limit: int, offset: int) -> tuple[int, int]:
    if not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE:
        raise ValidationError(f"'limit' must be between 1 and {MAX_PAGE}.")
    if not isinstance(offset, int) or offset < 0:
        raise ValidationError("'offset' must be zero or greater.")
    return limit, offset


def _peer_record(
    peer_id: str,
    *,
    public_key_hex: str | None = None,
    protocols: Iterable[str] = (),
    listen_addrs: Iterable[str] = (),
    agent_version: str | None = None,
    protocol_version: str | None = None,
    updated_at: float | None = None,
) -> dict[str, Any]:
    return {
        "peer_id": _check_peer_id(peer_id),
        "public_key_hex": public_key_hex,
        "protocol_version": protocol_version,
        "agent_version": agent_version,
        "protocols": [str(protocol) for protocol in protocols or ()],
        "listen_addrs": [str(addr) for addr in listen_addrs or ()],
        "updated_at": float(updated_at if updated_at is not None else time.time()),
    }


class MemoryPeerRepository:
    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._peers: dict[str, dict[str, Any]] = {}

    def upsert(self, peer_id: str, **fields: Any) -> dict[str, Any]:
        record = _peer_record(peer_id, **fields)
        with self._lock:
            self._peers[record["peer_id"]] = record
        return dict(record)

    def get(self, peer_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._peers.get(_check_peer_id(peer_id))
            return dict(record) if record else None

    def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit, offset = _check_page(limit, offset)
        with self._lock:
            records = sorted(
                self._peers.values(), key=lambda item: item["updated_at"], reverse=True
            )
            return [dict(record) for record in records[offset: offset + limit]]

    def delete(self, peer_id: str) -> bool:
        with self._lock:
            return self._peers.pop(_check_peer_id(peer_id), None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._peers)


class SqlitePeerRepository:
    backend = "sqlite"

    def __init__(self, connection: sqlite3.Connection, lock: threading.RLock):
        self._connection = connection
        self._lock = lock

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "peer_id": row["peer_id"],
            "public_key_hex": row["public_key"],
            "protocol_version": row["protocol_version"],
            "agent_version": row["agent_version"],
            "protocols": json.loads(row["protocols"] or "[]"),
            "listen_addrs": json.loads(row["listen_addrs"] or "[]"),
            "updated_at": row["updated_at"],
        }

    def upsert(self, peer_id: str, **fields: Any) -> dict[str, Any]:
        record = _peer_record(peer_id, **fields)
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO peers
                        (peer_id, public_key, protocol_version, agent_version,
                         protocols, listen_addrs, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(peer_id) DO UPDATE SET
                        public_key = excluded.public_key,
                        protocol_version = excluded.protocol_version,
                        agent_version = excluded.agent_version,
                        protocols = excluded.protocols,
                        listen_addrs = excluded.listen_addrs,
                        updated_at = excluded.updated_at
                    """,
                    (
                        record["peer_id"],
                        record["public_key_hex"],
                        record["protocol_version"],
                        record["agent_version"],
                        json.dumps(record["protocols"]),
                        json.dumps(record["listen_addrs"]),
                        record["updated_at"],
                    ),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Could not store peer metadata: {exc}") from exc
        return record

    def get(self, peer_id: str) -> dict[str, Any] | None:
        try:
            with self._lock:
                row = self._connection.execute(
                    "SELECT * FROM peers WHERE peer_id = ?", (_check_peer_id(peer_id),)
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read peer metadata: {exc}") from exc
        return self._row_to_record(row) if row is not None else None

    def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit, offset = _check_page(limit, offset)
        try:
            with self._lock:
                rows = self._connection.execute(
                    """
                    SELECT * FROM peers
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not list peer metadata: {exc}") from exc
        return [self._row_to_record(row) for row in rows]

    def delete(self, peer_id: str) -> bool:
        try:
            with self._lock, self._connection:
                cursor = self._connection.execute(
                    "DELETE FROM peers WHERE peer_id = ?", (_check_peer_id(peer_id),)
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StorageError(f"Could not delete peer metadata: {exc}") from exc

    def count(self) -> int:
        try:
            with self._lock:
                return self._connection.execute("SELECT COUNT(*) FROM peers").fetchone()[0]
        except sqlite3.Error as exc:
            raise StorageError(f"Could not count peers: {exc}") from exc


def _check_key(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValidationError("Setting key must be a non-empty string.")
    return key.strip()


class MemorySettingsRepository:
    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._values: dict[str, str] = {}

    def get(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            return self._values.get(_check_key(key), default)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._values[_check_key(key)] = str(value)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._values.pop(_check_key(key), None) is not None

    def all(self) -> dict[str, str]:
        with self._lock:
            return dict(self._values)


class SqliteSettingsRepository:
    backend = "sqlite"

    def __init__(self, connection: sqlite3.Connection, lock: threading.RLock):
        self._connection = connection
        self._lock = lock

    def get(self, key: str, default: str | None = None) -> str | None:
        try:
            with self._lock:
                row = self._connection.execute(
                    "SELECT value FROM settings WHERE key = ?", (_check_key(key),)
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read setting: {exc}") from exc
        return row["value"] if row is not None else default

    def set(self, key: str, value: str) -> None:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (_check_key(key), str(value), time.time()),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Could not write setting: {exc}") from exc

    def delete(self, key: str) -> bool:
        try:
            with self._lock, self._connection:
                cursor = self._connection.execute(
                    "DELETE FROM settings WHERE key = ?", (_check_key(key),)
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StorageError(f"Could not delete setting: {exc}") from exc

    def all(self) -> dict[str, str]:
        try:
            with self._lock:
                rows = self._connection.execute("SELECT key, value FROM settings").fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not list settings: {exc}") from exc
        return {row["key"]: row["value"] for row in rows}
