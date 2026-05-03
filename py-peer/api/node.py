"""
Node info endpoints.

GET /api/v1/node/info     - peer ID, nickname, multiaddr, port, ready state
GET /api/v1/node/status   - running, ready, uptime
GET /api/v1/node/multiaddr - full multiaddr string
"""

import time
from .base import BaseHandler

_start_time = time.time()


class NodeInfoHandler(BaseHandler):
    """GET /api/v1/node/info"""

    def get(self):
        if not self.require_ready():
            return
        info = self.service.get_connection_info()
        self.send_success({
            "peer_id": info.get("peer_id"),
            "nickname": info.get("nickname"),
            "multiaddr": info.get("multiaddr"),
            "port": self.service.port,
            "ready": self.service.ready,
            "uptime_seconds": round(time.time() - _start_time, 1),
        })


class NodeStatusHandler(BaseHandler):
    """GET /api/v1/node/status"""

    def get(self):
        self.send_success({
            "ready": self.service.ready,
            "running": self.service.running,
            "uptime_seconds": round(time.time() - _start_time, 1),
            "port": self.service.port,
            "strict_signing": self.service.strict_signing,
            "nickname": self.service.nickname,
            "topic": self.service.topic,
        })


class NodeMultiaddrHandler(BaseHandler):
    """GET /api/v1/node/multiaddr"""

    def get(self):
        if not self.require_ready():
            return
        self.send_success({
            "multiaddr": self.service.full_multiaddr,
        })
