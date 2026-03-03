"""
Service control endpoints.

GET  /api/v1/service/status    - overall health, readiness, uptime
GET  /api/v1/service/config    - current configuration
POST /api/v1/service/stop      - gracefully stop the HeadlessService
POST /api/v1/service/bootstrap - re-trigger bootstrap connections
"""

import time
import asyncio
from .base import BaseHandler

_start_time = time.time()


class ServiceStatusHandler(BaseHandler):
    """GET /api/v1/service/status"""

    def get(self):
        self.send_success({
            "ready": self.service.ready,
            "running": self.service.running,
            "uptime_seconds": round(time.time() - _start_time, 1),
            "peer_count": self.service.get_connection_info().get("peer_count", 0) if self.service.ready else 0,
        })


class ServiceConfigHandler(BaseHandler):
    """GET /api/v1/service/config"""

    def get(self):
        self.send_success({
            "nickname": self.service.nickname,
            "port": self.service.port,
            "topic": self.service.topic,
            "strict_signing": self.service.strict_signing,
            "download_dir": self.service.download_dir,
            "connect_addrs": self.service.connect_addrs,
        })


class ServiceStopHandler(BaseHandler):
    """POST /api/v1/service/stop — graceful shutdown"""

    def post(self):
        if not self.service:
            self.send_error_response("No service attached.", status=503)
            return
        # Schedule the stop coroutine without blocking the handler
        asyncio.get_event_loop().call_soon(self._do_stop)
        self.send_success({"message": "Stop signal sent to HeadlessService."})

    def _do_stop(self):
        """Fire-and-forget the stop signal via threading."""
        import threading
        def _stop():
            import trio
            # The service's stop_event is a trio.Event; set it from another
            # thread via the sync API if available, otherwise notify via a flag.
            try:
                self.service.running = False
                self.service.stop_event.set()
            except Exception:
                self.service.running = False
        threading.Thread(target=_stop, daemon=True).start()


class ServiceBootstrapHandler(BaseHandler):
    """POST /api/v1/service/bootstrap — re-trigger bootstrap peer connections"""

    def post(self):
        if not self.require_ready():
            return
        # Queue connection requests for all bootstrap peers
        from headless import BOOTSTRAP_PEERS
        count = 0
        for addr in BOOTSTRAP_PEERS:
            if self.service.connect_to_peer(addr):
                count += 1
        self.send_success({
            "message": f"Queued connections to {count} bootstrap peers.",
            "bootstrap_peers_count": count,
        }, status=202)
