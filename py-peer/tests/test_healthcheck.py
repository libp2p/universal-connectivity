"""Unit tests for the container readiness healthcheck probe."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.healthcheck import check_health


class _StatusHandler(BaseHTTPRequestHandler):
    """Small endpoint that mimics /api/v1/service/status."""

    def do_GET(self):  # noqa: N802 - http.server naming
        payload = {
            "/ready": {"data": {"ready": True, "running": True, "failed": False}},
            "/not-ready": {"data": {"ready": False, "running": True, "failed": False}},
            "/not-running": {"data": {"ready": True, "running": False, "failed": False}},
            "/failed": {"data": {"ready": True, "running": True, "failed": True}},
            "/no-data": {"success": True, "data": None},
        }.get(self.path)

        if self.path == "/http-500":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"boom")
            return

        body = json.dumps(payload if payload is not None else {"data": {}}).encode()
        if self.path == "/not-json":
            body = b"<html>not json</html>"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class HealthcheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _StatusHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_healthy_only_when_ready_and_running(self):
        self.assertTrue(check_health(f"{self.base}/ready"))
        self.assertFalse(check_health(f"{self.base}/not-ready"))
        self.assertFalse(check_health(f"{self.base}/not-running"))
        self.assertFalse(check_health(f"{self.base}/failed"))

    def test_malformed_and_error_responses_are_unhealthy(self):
        self.assertFalse(check_health(f"{self.base}/not-json"))
        self.assertFalse(check_health(f"{self.base}/no-data"))
        self.assertFalse(check_health(f"{self.base}/http-500"))
        self.assertFalse(check_health(f"{self.base}/missing"))

    def test_connection_failure_is_unhealthy(self):
        # Port 1 on loopback is not served by a healthy peer.
        self.assertFalse(check_health("http://127.0.0.1:1/api/v1/service/status", timeout=1))


if __name__ == "__main__":
    unittest.main()
