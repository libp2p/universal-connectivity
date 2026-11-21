"""
Peer management endpoints.

GET    /api/v1/peers                  - list connected peers
GET    /api/v1/peers/count            - count of connected peers
GET    /api/v1/peers/known            - peers in peerstore
POST   /api/v1/peers/connect          - connect via multiaddr
GET    /api/v1/peers/{peer_id}        - info for a specific peer
GET    /api/v1/peers/{peer_id}/identify - identify protocol info (from cache)
"""

from .base import BaseHandler, parse_string_field


class PeerListHandler(BaseHandler):
    """GET /api/v1/peers"""

    def get(self) -> None:
        if not self.require_ready():
            return
        peers = self.peer_service.connected_peers()
        self.send_success({
            "peers": peers,
            "count": len(peers),
        })


class PeerCountHandler(BaseHandler):
    """GET /api/v1/peers/count"""

    def get(self) -> None:
        if not self.require_ready():
            return
        self.send_success({"count": self.peer_service.peer_count()})


class KnownPeersHandler(BaseHandler):
    """GET /api/v1/peers/known"""

    def get(self) -> None:
        if not self.require_ready():
            return
        known = self.peer_service.known_peers()
        self.send_success({"peers": known, "count": len(known)})


class PeerConnectHandler(BaseHandler):
    """POST /api/v1/peers/connect"""

    def post(self) -> None:
        if not self.require_ready():
            return
        body = self.get_json_body()
        try:
            maddr = parse_string_field(body, "multiaddr", required=True)
        except ValueError as e:
            self.send_error_response(str(e))
            return
        result = self.connection_service.connect(maddr)
        self.send_success(result, status=202)


class PeerDetailHandler(BaseHandler):
    """GET /api/v1/peers/{peer_id}"""

    def get(self, peer_id: str) -> None:
        if not self.require_ready():
            return
        self.send_success(self.peer_service.peer_detail(peer_id))


class PeerIdentifyHandler(BaseHandler):
    """GET /api/v1/peers/{peer_id}/identify — returns cached identify data"""

    def get(self, peer_id: str) -> None:
        if not self.require_ready():
            return
        self.send_success(self.identity_service.get(peer_id))
