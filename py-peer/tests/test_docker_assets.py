"""Container packaging regression tests.

These tests inspect the Docker assets without requiring a Docker daemon and
exercise the health-check logic against a local HTTP server.
"""

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.healthcheck import check_health

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


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


class DockerfileTests(unittest.TestCase):
    def setUp(self):
        self.text = _read("Dockerfile")

    def test_multi_stage_locked_build(self):
        self.assertIn("AS builder", self.text)
        self.assertIn("AS runtime", self.text)
        self.assertIn("uv sync --frozen --no-dev --no-install-project", self.text)
        self.assertIn("ghcr.io/astral-sh/uv:", self.text)

    def test_runs_unprivileged_with_volume_and_entrypoint(self):
        self.assertIn("USER uc", self.text)
        self.assertIn("groupadd --gid 10001 uc", self.text)
        self.assertIn("VOLUME [\"/data\"]", self.text)
        self.assertIn("UC_DATA_DIR=/data", self.text)
        self.assertIn('ENTRYPOINT ["python", "main.py"]', self.text)
        self.assertIn("HEALTHCHECK", self.text)

    def test_only_tcp_ports_and_no_secrets(self):
        self.assertIn("EXPOSE 4001/tcp 4001/udp 4002/udp 4003/udp 8765/tcp", self.text)
        self.assertNotIn("node_modules", self.text)


class DockerignoreTests(unittest.TestCase):
    def test_excludes_local_state_and_build_context_noise(self):
        lines = {
            line.strip()
            for line in _read(".dockerignore").splitlines()
            if line.strip() and not line.startswith("#")
        }
        for required in (
            ".git",
            ".venv/",
            ".env",
            "__pycache__/",
            "system_messages.txt",
            "node_modules/",
            "tests/",
        ):
            self.assertIn(required, lines)


class ComposeTests(unittest.TestCase):
    def setUp(self):
        compose_file = (
            "docker-compose.yml"
            if os.path.exists(os.path.join(ROOT, "docker-compose.yml"))
            else "compose.yaml"
        )
        self.text = _read(compose_file)

    def test_service_contract(self):
        self.assertIn("restart: unless-stopped", self.text)
        self.assertIn("init: true", self.text)
        self.assertIn("UC_DATA_DIR: /data", self.text)
        self.assertIn("uc-data:/data", self.text)
        self.assertIn("healthcheck:", self.text)
        self.assertIn("/app/core/healthcheck.py", self.text)
        self.assertIn("max-size:", self.text)
        self.assertIn("max-file:", self.text)

    def test_ports_are_limited_and_api_defaults_to_loopback(self):
        self.assertIn(
            '"${UC_API_PUBLISH_HOST:-127.0.0.1}:${UC_API_PORT:-8765}:${UC_API_PORT:-8765}"',
            self.text,
        )
        self.assertIn('"${UC_PEER_PORT:-4001}:${UC_PEER_PORT:-4001}/tcp"', self.text)

    def test_announce_host_is_configurable(self):
        self.assertIn("UC_ANNOUNCE_HOST", self.text)
        self.assertIn("--announce-host", self.text)
        self.assertIn("${UC_ANNOUNCE_HOST:-127.0.0.1}", self.text)


if __name__ == "__main__":
    unittest.main()
