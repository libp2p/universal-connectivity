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

    def get(self):
        if not self.require_ready():
            return
        cache = self.service.peer_info_cache
        result = {}
        for peer_id, info in cache.items():
            result[peer_id] = {
                "protocol_version": info.get("protocol_version"),
                "agent_version": info.get("agent_version"),
                "listen_addrs": [str(a) for a in info.get("listen_addrs", [])],
                "protocols": [str(p) for p in info.get("protocols", [])],
                "cached_at": info.get("timestamp"),
            }
        self.send_success({"cache": result, "count": len(result)})


class IdentityPeerHandler(BaseHandler):
    """GET /api/v1/identity/{peer_id}"""

    def get(self, peer_id):
        if not self.require_ready():
            return
        info = self.service.peer_info_cache.get(peer_id)
        if not info:
            self.send_error_response(
                f"No cached identify info for peer '{peer_id[:16]}...'. "
                "Connect to the peer first so that the identify protocol is triggered automatically.",
                status=404,
            )
            return
        self.send_success({
            "peer_id": peer_id,
            "protocol_version": info.get("protocol_version"),
            "agent_version": info.get("agent_version"),
            "listen_addrs": [str(a) for a in info.get("listen_addrs", [])],
            "protocols": [str(p) for p in info.get("protocols", [])],
            "cached_at": info.get("timestamp"),
        })


class IdentityPublicKeyHandler(BaseHandler):
    """GET /api/v1/identity/{peer_id}/pubkey"""

    def get(self, peer_id):
        if not self.require_ready():
            return
        pubkey = self.service.get_public_key_for_peer(peer_id)
        if pubkey is None:
            self.send_error_response(
                f"No public key cached for peer '{peer_id[:16]}...'.", status=404
            )
            return
        # public key may be bytes or an object — safely convert to hex
        if isinstance(pubkey, bytes):
            pubkey_hex = pubkey.hex()
        else:
            pubkey_hex = str(pubkey)
        self.send_success({"peer_id": peer_id, "public_key_hex": pubkey_hex})


class IdentityCacheDeleteHandler(BaseHandler):
    """DELETE /api/v1/identity/{peer_id}/cache"""

    def delete(self, peer_id):
        if not self.require_ready():
            return
        if peer_id in self.service.peer_info_cache:
            del self.service.peer_info_cache[peer_id]
            self.send_success({"message": f"Cache entry for '{peer_id[:16]}...' deleted."})
        else:
            self.send_error_response(
                f"No cache entry found for peer '{peer_id[:16]}...'.", status=404
            )
