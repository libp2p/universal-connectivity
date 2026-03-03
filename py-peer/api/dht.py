"""
DHT endpoints.

GET /api/v1/dht/status         - mode, routing table size, random walk
GET /api/v1/dht/peers          - peer IDs in DHT routing table
GET /api/v1/dht/routing-table  - concise routing table dump
"""

from .base import BaseHandler


class DHTStatusHandler(BaseHandler):
    """GET /api/v1/dht/status"""

    def get(self):
        if not self.require_ready():
            return
        dht = self.service.dht
        if not dht:
            self.send_error_response("DHT is not initialised.", status=503)
            return
        try:
            rt_size = len(list(dht.routing_table.get_peer_ids()))
        except Exception:
            rt_size = -1

        # DHTMode enum → string
        mode_val = getattr(dht, "mode", None)
        mode_str = mode_val.name if hasattr(mode_val, "name") else str(mode_val)

        self.send_success({
            "mode": mode_str,
            "random_walk_enabled": getattr(dht, "enable_random_walk", False),
            "routing_table_size": rt_size,
        })


class DHTPeersHandler(BaseHandler):
    """GET /api/v1/dht/peers"""

    def get(self):
        if not self.require_ready():
            return
        dht = self.service.dht
        if not dht:
            self.send_error_response("DHT is not initialised.", status=503)
            return
        try:
            peers = [str(p) for p in dht.routing_table.get_peer_ids()]
        except Exception as e:
            self.send_error_response(f"Could not read routing table: {e}", status=500)
            return
        self.send_success({"peers": peers, "count": len(peers)})


class DHTRoutingTableHandler(BaseHandler):
    """GET /api/v1/dht/routing-table"""

    def get(self):
        if not self.require_ready():
            return
        dht = self.service.dht
        if not dht:
            self.send_error_response("DHT is not initialised.", status=503)
            return
        try:
            peers = [str(p) for p in dht.routing_table.get_peer_ids()]
        except Exception as e:
            self.send_error_response(f"Could not read routing table: {e}", status=500)
            return
        self.send_success({
            "routing_table": peers,
            "total_peers": len(peers),
        })
