"""Local identity and cached Identify-protocol metadata.

The service owns key resolution (seed / persisted / created / ephemeral) and
the identify cache. The engine only exposes the transport host; adapters keep
receiving the same serialized views they did before.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.identity.identify.identify import (
    parse_identify_response,
    ID as IDENTIFY_PROTOCOL_ID,
)
from libp2p.identity_utils import (
    create_new_ed25519_key_pair,
    load_identity as load_identity_file,
    save_identity,
)
from libp2p.peer.id import ID
from libp2p.utils.varint import read_length_prefixed_protobuf

from ..errors import NotFoundError, ValidationError
from ..models import PeerIdentity

logger = logging.getLogger("app.services.identity")

# Cached identify responses older than this are refreshed on demand.
CACHE_TTL_SECONDS = 300.0


def _save_identity_atomically(key_pair: Any, path: Path) -> None:
    """Persist a private key without leaving a half-written file behind.

    ``save_identity`` writes the libp2p protobuf format and sets mode 0600 on
    POSIX. Writing to a sibling temp file and renaming means a crash or a full
    disk leaves the previous identity intact instead of an unreadable key.
    """
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        save_identity(key_pair, temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


class IdentityService:
    """Resolve the local key pair and cache Identify-protocol metadata.

    Private key material is never read or returned by the query methods; the
    engine receives the key pair once at startup. Public keys are returned only
    as hex strings through the adapter-facing API.
    """

    def __init__(self, engine: Any) -> None:
        self._engine = engine
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @property
    def engine(self) -> Any:
        return self._engine

    # ------------------------------------------------------------------ #
    #  Local identity
    # ------------------------------------------------------------------ #
    def identity(self) -> PeerIdentity:
        return PeerIdentity(
            peer_id=str(self._engine.host.get_id()),
            nickname=self._engine.nickname,
        )

    def peer_id(self) -> str:
        return str(self._engine.host.get_id())

    def load_identity(self) -> Any:
        """Return the key pair this host runs with.

        Resolution order is deliberate, because the peer ID is derived from the
        key and other peers dial and address us by it:

        1. An explicit ``--seed`` uses a deterministic key and never touches
           disk. This keeps the historical development/test behaviour and lets
           callers request a stable peer ID.
        2. An existing identity file is loaded as-is. This is what makes the
           peer ID survive a restart, even if ``--seed`` is added or removed.
        3. No file yet generates one fresh Ed25519 key and persists it with
           mode 0600.

        Without a data directory the identity is ephemeral and the peer ID
        changes on restart; that is logged as a warning. A corrupt identity
        file fails startup instead of silently minting a different peer ID.
        """
        engine = self._engine
        if engine.seed:
            engine.identity_source = "seed"
            logger.info(
                "Using a deterministic identity from an explicit --seed "
                "(the seed value is not logged)"
            )
            return create_new_key_pair(
                seed=hashlib.sha256(engine.seed.encode()).digest()
            )

        path = Path(engine.identity_path) if engine.identity_path else None
        if path is not None and path.is_file():
            try:
                key_pair = load_identity_file(path)
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    f"Stored peer identity is unreadable: {path} ({exc}). "
                    "Restore it from backup, or delete it to create a new "
                    "identity (this changes the peer ID other peers dial)."
                ) from exc
            engine.identity_source = "persisted"
            logger.info(f"Loaded persisted peer identity from {path}")
            return key_pair

        key_pair = create_new_ed25519_key_pair()
        if path is None:
            engine.identity_source = "ephemeral"
            logger.warning(
                "No data directory configured; using an ephemeral peer "
                "identity, so the peer ID will change on restart. Pass "
                "--data-dir or set UC_DATA_DIR to keep it."
            )
            return key_pair

        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _save_identity_atomically(key_pair, path)
        except OSError as exc:
            raise RuntimeError(
                f"Could not persist the peer identity at {path}: {exc}. "
                "Choose a writable data directory with --data-dir or "
                "UC_DATA_DIR."
            ) from exc
        engine.identity_source = "created"
        logger.info(f"Created a new peer identity at {path} (mode 0600)")
        return key_pair

    # ------------------------------------------------------------------ #
    #  Identify protocol
    # ------------------------------------------------------------------ #
    async def fetch_peer_info(self, peer_id: Any) -> Any:
        """Get peer information using the official identify protocol."""
        try:
            logger.info(f"🔍 Requesting identify info from peer: {peer_id}")
            peerstore = self._engine.host.get_peerstore()
            logger.info(f"peers in peer store are: {peerstore.peers_with_addrs()}")
            logger.info(
                f"address of peer {peer_id} is "
                f"{peerstore.peer_info(peer_id).addrs} "
            )

            # Use tuple format as in the reference example.
            stream = await self._engine.host.new_stream(
                peer_id, (IDENTIFY_PROTOCOL_ID,)
            )

            try:
                response_bytes = await read_length_prefixed_protobuf(
                    stream, use_varint_format=True
                )

                if not response_bytes:
                    logger.warning(f"Empty identify response from peer: {peer_id}")
                    return None

                identify_info = parse_identify_response(response_bytes)

                logger.info(f"✅ Received identify info from {peer_id}")
                logger.info(
                    f"  - Protocol Version: {identify_info.protocol_version}"
                )
                logger.info(f"  - Agent Version: {identify_info.agent_version}")
                logger.info(f"  - Public Key: {len(identify_info.public_key)} bytes")
                logger.info(
                    f"  - Listen Addresses: {len(identify_info.listen_addrs)} addresses"
                )
                logger.info(f"  - Protocols: {len(identify_info.protocols)} protocols")

                with self._lock:
                    self._cache[str(peer_id)] = {
                        "public_key": identify_info.public_key,
                        "protocol_version": identify_info.protocol_version,
                        "agent_version": identify_info.agent_version,
                        "listen_addrs": identify_info.listen_addrs,
                        "protocols": identify_info.protocols,
                        "timestamp": time.time(),
                    }

                return identify_info

            finally:
                await stream.close()

        except Exception as e:
            logger.error(f"❌ Failed to get identify info from peer {peer_id}: {e}")
            return None

    async def cached_peer_info(
        self, peer_id: str
    ) -> dict[str, Any] | None:
        """Get cached peer info, or fetch it if unavailable/stale."""
        peer_id_str = str(peer_id)

        with self._lock:
            cached_info = self._cache.get(peer_id_str)
        if cached_info and time.time() - cached_info["timestamp"] < CACHE_TTL_SECONDS:
            return dict(cached_info)
        if cached_info:
            logger.debug(f"Cached info for {peer_id_str} is stale, refreshing")

        try:
            peer_id_obj = (
                ID.from_base58(peer_id_str) if isinstance(peer_id, str) else peer_id
            )
            identify_info = await self.fetch_peer_info(peer_id_obj)

            if identify_info:
                with self._lock:
                    info = self._cache.get(peer_id_str)
                    return dict(info) if info else None
        except Exception as e:
            logger.error(f"❌ Failed to get peer info for {peer_id_str}: {e}")

        return None

    # Compatibility aliases for the previous engine method names.
    async def get_peer_info_via_identify(self, peer_id: Any) -> Any:
        return await self.fetch_peer_info(peer_id)

    async def get_cached_peer_info(
        self, peer_id: str
    ) -> dict[str, Any] | None:
        return await self.cached_peer_info(peer_id)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Snapshot the raw identify cache for API/engine readout."""
        with self._lock:
            return {peer_id: dict(info) for peer_id, info in self._cache.items()}

    def raw_get(self, peer_id: str) -> dict[str, Any] | None:
        with self._lock:
            info = self._cache.get(peer_id)
            return dict(info) if info else None

    def raw_delete(self, peer_id: str) -> bool:
        with self._lock:
            return self._cache.pop(peer_id, None) is not None

    def raw_public_key(self, peer_id: str) -> Any:
        with self._lock:
            info = self._cache.get(peer_id)
            return info.get("public_key") if info else None

    # ------------------------------------------------------------------ #
    #  Serialized adapter-facing views
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_peer_id(peer_id: str) -> str:
        if not isinstance(peer_id, str) or not peer_id.strip():
            raise ValidationError("Peer ID is required.")
        return peer_id.strip()

    @staticmethod
    def _serialize(
        peer_id: str, info: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "peer_id": peer_id,
            "protocol_version": info.get("protocol_version"),
            "agent_version": info.get("agent_version"),
            "listen_addrs": [str(addr) for addr in info.get("listen_addrs", [])],
            "protocols": [str(proto) for proto in info.get("protocols", [])],
            "cached_at": info.get("timestamp"),
        }

    def cache(self) -> dict[str, Any]:
        return {
            peer_id: self._serialize(peer_id, info)
            for peer_id, info in self.snapshot().items()
        }

    def get(self, peer_id: str) -> dict[str, Any]:
        peer_id = self._normalize_peer_id(peer_id)
        info = self.raw_get(peer_id)
        if not info:
            raise NotFoundError(
                f"No cached identify info for peer '{peer_id[:16]}...'. "
                "Connect to the peer first so that the identify protocol is "
                "triggered automatically."
            )
        return self._serialize(peer_id, info)

    def public_key_hex(self, peer_id: str) -> str:
        peer_id = self._normalize_peer_id(peer_id)
        pubkey = self.raw_public_key(peer_id)
        if pubkey is None:
            raise NotFoundError(
                f"No public key cached for peer '{peer_id[:16]}...'."
            )
        return pubkey.hex() if isinstance(pubkey, bytes) else str(pubkey)

    def invalidate(self, peer_id: str) -> None:
        peer_id = self._normalize_peer_id(peer_id)
        if not self.raw_delete(peer_id):
            raise NotFoundError(f"No cache entry found for peer '{peer_id[:16]}...'.")
