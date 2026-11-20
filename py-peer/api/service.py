"""
Service control endpoints.

GET  /api/v1/service/status    - overall health, readiness, uptime
GET  /api/v1/service/config    - current configuration
POST /api/v1/service/stop      - gracefully stop the shared runtime
POST /api/v1/service/bootstrap - re-trigger bootstrap connections

These handlers only translate HTTP to ApplicationRuntime calls; lifecycle and
configuration logic live in the runtime/service layer.
"""

from .base import BaseHandler


class ServiceStatusHandler(BaseHandler):
    """GET /api/v1/service/status"""

    def get(self) -> None:
        status = self.runtime.status()
        self.send_success({
            "state": status.state,
            "ready": status.ready,
            "running": status.running,
            "failed": status.failed,
            "uptime_seconds": status.uptime_seconds,
            "peer_count": status.peer_count,
            "peer_id": status.peer_id,
            "nickname": status.nickname,
        })


class ServiceConfigHandler(BaseHandler):
    """GET /api/v1/service/config"""

    def get(self) -> None:
        self.send_success(self.runtime.config_snapshot())


class ServiceStopHandler(BaseHandler):
    """POST /api/v1/service/stop — graceful shutdown"""

    def post(self) -> None:
        # ``request_stop`` only sets a thread-safe event. The trio thread that
        # owns the host performs the teardown, so this returns immediately.
        self.runtime.request_stop()
        self.send_success({"message": "Stop signal sent to the application runtime."})


class ServiceBootstrapHandler(BaseHandler):
    """POST /api/v1/service/bootstrap — re-trigger bootstrap peer connections"""

    def post(self) -> None:
        if not self.require_ready():
            return
        self.send_success(self.discovery_service.bootstrap(), status=202)
