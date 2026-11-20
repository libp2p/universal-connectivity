"""Versioned SQLite schema migrations.

The database is a local, single-process store. Version history lives in
``PRAGMA user_version`` so opening a database never guesses its shape, and a
database written by a newer build is refused instead of being corrupted.
"""

from __future__ import annotations

import sqlite3

from ..errors import StorageError

SCHEMA_VERSION = 1

_MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    topic       TEXT NOT NULL,
    sender_id   TEXT NOT NULL,
    sender_nick TEXT NOT NULL,
    content     TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'chat_message',
    timestamp   REAL NOT NULL,
    received_at REAL NOT NULL,
    read        INTEGER NOT NULL DEFAULT 0,
    file_cid    TEXT,
    file_name   TEXT,
    file_size   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_messages_topic ON messages(topic);

CREATE TABLE IF NOT EXISTS peers (
    peer_id          TEXT PRIMARY KEY,
    public_key       TEXT,
    protocol_version TEXT,
    agent_version    TEXT,
    protocols        TEXT NOT NULL DEFAULT '[]',
    listen_addrs     TEXT NOT NULL DEFAULT '[]',
    updated_at       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.executescript(_MIGRATION_1)


MIGRATIONS = {1: _migration_1}


def migrate(connection: sqlite3.Connection) -> int:
    """Apply pending migrations and return the resulting schema version."""
    current = connection.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise StorageError(
            f"Storage schema v{current} is newer than this build supports "
            f"(v{SCHEMA_VERSION}). Upgrade py-peer or use a different "
            "storage path."
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        with connection:
            MIGRATIONS[version](connection)
            # PRAGMA does not accept bound parameters; the value is an
            # integer from this module, never user input.
            connection.execute(f"PRAGMA user_version = {version}")
    return SCHEMA_VERSION
