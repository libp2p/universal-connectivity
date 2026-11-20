"""Typed result models returned by services.

These are plain dataclasses with ``to_dict()``; they do not depend on Tornado,
Textual, or MCP. Adapters decide the wire/UI representation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .constants import DEFAULT_PORT


@dataclass(frozen=True)
class PeerIdentity:
    """Local peer identity (never contains private key material)."""

    peer_id: str
    nickname: str

    def to_dict(self) -> dict[str, Any]:
        return {"peer_id": self.peer_id, "nickname": self.nickname}


@dataclass(frozen=True)
class ConnectionSummary:
    """Snapshot of the local node's connection state."""

    peer_id: str
    nickname: str
    multiaddr: str | None
    multiaddrs: list[str] = field(default_factory=list)
    listen_addrs: list[str] = field(default_factory=list)
    connected_peers: list[str] = field(default_factory=list)

    @property
    def peer_count(self) -> int:
        return len(self.connected_peers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "nickname": self.nickname,
            "multiaddr": self.multiaddr,
            "multiaddrs": list(self.multiaddrs),
            "listen_addrs": list(self.listen_addrs),
            "connected_peers": list(self.connected_peers),
            "peer_count": self.peer_count,
        }


@dataclass(frozen=True)
class ServiceStatus:
    """Health snapshot of the shared runtime."""

    state: str
    ready: bool
    running: bool
    failed: bool
    peer_id: str | None
    nickname: str
    port: int
    topic: str | None
    strict_signing: bool
    uptime_seconds: float
    peer_count: int
    multiaddrs: list[str] = field(default_factory=list)
    listen_addrs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "ready": self.ready,
            "running": self.running,
            "failed": self.failed,
            "peer_id": self.peer_id,
            "nickname": self.nickname,
            "port": self.port,
            "topic": self.topic,
            "strict_signing": self.strict_signing,
            "uptime_seconds": self.uptime_seconds,
            "peer_count": self.peer_count,
            "multiaddrs": list(self.multiaddrs),
            "listen_addrs": list(self.listen_addrs),
        }


@dataclass(frozen=True)
class RuntimeConfig:
    """Configuration used to construct the shared runtime.

    Mirrors the CLI/host options validated in earlier phases; kept separate so
    adapters do not need to know HeadlessService constructor details.
    """

    nickname: str
    port: int = DEFAULT_PORT
    connect_addrs: list[str] = field(default_factory=list)
    ui_mode: bool = False
    strict_signing: bool = True
    seed: str | None = None
    topic: str | None = None
    announce_host: str = "127.0.0.1"
    listen_addrs: list[str] | None = None
    announce_addrs: list[str] | None = None
    storage_path: str | None = None
    data_dir: str | None = None
    min_connections: int = 50
    low_watermark: int = 400
    high_watermark: int = 450
    max_connections: int = 500

    @classmethod
    def from_namespace(cls, args: Any) -> "RuntimeConfig":
        """Build a config from an argparse namespace (or any attr container)."""
        return cls(
            nickname=getattr(args, "nick", None) or f"peer-{int(time.time())}",
            port=getattr(args, "port", 0) or 0,
            connect_addrs=list(getattr(args, "connect", None) or []),
            ui_mode=bool(getattr(args, "ui", False)),
            strict_signing=not bool(getattr(args, "no_strict_signing", False)),
            seed=getattr(args, "seed", None),
            topic=getattr(args, "topic", None),
            announce_host=getattr(args, "announce_host", "127.0.0.1"),
            listen_addrs=list(getattr(args, "listen_addrs", None) or []) or None,
            announce_addrs=list(getattr(args, "announce_addrs", None) or []) or None,
            storage_path=getattr(args, "storage_path", None) or None,
            data_dir=getattr(args, "data_dir", None) or None,
            min_connections=int(getattr(args, "min_connections", 50) or 50),
            low_watermark=int(getattr(args, "low_watermark", 400) or 400),
            high_watermark=int(getattr(args, "high_watermark", 450) or 450),
            max_connections=int(getattr(args, "max_connections", 500) or 500),
        )

    def service_kwargs(self, *, identity_path: str | None = None) -> dict[str, Any]:
        """Keyword arguments for ``HeadlessService``.

        ``identity_path`` is injected by the runtime after the data directory
        has been resolved; ``seed`` stays an explicit, deterministic override.
        """
        return {
            "nickname": self.nickname,
            "port": self.port,
            "connect_addrs": list(self.connect_addrs),
            "ui_mode": self.ui_mode,
            "strict_signing": self.strict_signing,
            "seed": self.seed,
            "topic": self.topic,
            "announce_host": self.announce_host,
            "listen_addrs": self.listen_addrs,
            "announce_addrs": self.announce_addrs,
            "identity_path": identity_path,
            "min_connections": self.min_connections,
            "low_watermark": self.low_watermark,
            "high_watermark": self.high_watermark,
            "max_connections": self.max_connections,
        }
