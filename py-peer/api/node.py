"""
Node info endpoints.

GET /api/v1/node/info     - peer ID, nickname, multiaddr(s), port, ready state
GET /api/v1/node/status   - running, ready, uptime
GET /api/v1/node/multiaddr - advertised multiaddr(s) and bound listen addresses
"""

from .base import BaseHandler


class NodeInfoHandler(BaseHandler):
    """GET /api/v1/node/info"""

    def get(self) -> None:
        if not self.require_ready():
            return
        info = self.peer_service.connection_info()
        self.send_success({
            "peer_id": info.peer_id,
            "nickname": info.nickname,
            "multiaddr": info.multiaddr,
            "multiaddrs": list(info.multiaddrs),
            "listen_addrs": list(info.listen_addrs),
            "port": self.service.port,
            "ready": self.runtime.ready,
            "uptime_seconds": self.runtime.uptime_seconds,
        })


class NodeStatusHandler(BaseHandler):
    """GET /api/v1/node/status"""

    def get(self) -> None:
        status = self.runtime.status()
        self.send_success({
            "ready": status.ready,
            "running": status.running,
            "uptime_seconds": status.uptime_seconds,
            "port": status.port,
            "strict_signing": status.strict_signing,
            "nickname": status.nickname,
            "topic": status.topic,
        })


class NodeMultiaddrHandler(BaseHandler):
    """GET /api/v1/node/multiaddr"""

    def get(self) -> None:
        if not self.require_ready():
            return
        multiaddrs = self.peer_service.advertised_addrs()
        listen_addrs = self.peer_service.listening_addrs()
        self.send_success({
            "multiaddr": multiaddrs[0] if multiaddrs else None,
            "multiaddrs": multiaddrs,
            "listen_addrs": listen_addrs,
        })
