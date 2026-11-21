"""
Identity / Identify-protocol endpoints.

GET    /api/v1/identity/cache              - list all cached identify entries
GET    /api/v1/identity/{peer_id}          - cached info (returns 404 if not cached)
GET    /api/v1/identity/{peer_id}/pubkey   - public key bytes (hex) from cache
DELETE /api/v1/identity/{peer_id}/cache    - invalidate cached entry
"""

from .base import BaseHandler


class IdentityCacheListHandler(BaseHandler):
    """GET /api/v1/identity/cache"""

    def get(self) -> None:
        if not self.require_ready():
            return
        cache = self.identity_service.cache()
        self.send_success({"cache": cache, "count": len(cache)})


class IdentityPeerHandler(BaseHandler):
    """GET /api/v1/identity/{peer_id}"""

    def get(self, peer_id: str) -> None:
        if not self.require_ready():
            return
        self.send_success(self.identity_service.get(peer_id))


class IdentityPublicKeyHandler(BaseHandler):
    """GET /api/v1/identity/{peer_id}/pubkey"""

    def get(self, peer_id: str) -> None:
        if not self.require_ready():
            return
        pubkey_hex = self.identity_service.public_key_hex(peer_id)
        self.send_success({"peer_id": peer_id, "public_key_hex": pubkey_hex})


class IdentityCacheDeleteHandler(BaseHandler):
    """DELETE /api/v1/identity/{peer_id}/cache"""

    def delete(self, peer_id: str) -> None:
        if not self.require_ready():
            return
        self.identity_service.invalidate(peer_id)
        self.send_success({"message": f"Cache entry for '{peer_id[:16]}...' deleted."})
