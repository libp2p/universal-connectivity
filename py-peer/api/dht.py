"""
DHT endpoints.

GET /api/v1/dht/status         - mode, routing table size, random walk
GET /api/v1/dht/peers          - peer IDs in DHT routing table
GET /api/v1/dht/routing-table  - concise routing table dump
"""

from .base import BaseHandler


class DHTStatusHandler(BaseHandler):
    """GET /api/v1/dht/status"""

    def get(self) -> None:
        if not self.require_ready():
            return
        self.send_success(self.discovery_service.dht_status())


class DHTPeersHandler(BaseHandler):
    """GET /api/v1/dht/peers"""

    def get(self) -> None:
        if not self.require_ready():
            return
        peers = self.discovery_service.dht_peers()
        self.send_success({"peers": peers, "count": len(peers)})


class DHTRoutingTableHandler(BaseHandler):
    """GET /api/v1/dht/routing-table"""

    def get(self) -> None:
        if not self.require_ready():
            return
        peers = self.discovery_service.dht_peers()
        self.send_success({
            "routing_table": peers,
            "total_peers": len(peers),
        })
