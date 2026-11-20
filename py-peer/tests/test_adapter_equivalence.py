"""Adapter equivalence: direct services and HTTP expose the same behaviour.

The HTTP handlers are thin translations of ``ApplicationRuntime`` services.
These tests drive representative operations through both paths and compare the
domain outcome, so a handler cannot silently grow its own business logic.
"""

from __future__ import annotations

import json
import queue
import threading
import unittest
from types import SimpleNamespace

from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.peer.id import ID
from tornado.testing import AsyncHTTPTestCase

from app import ApplicationRuntime
from app.errors import ValidationError
from app.services.messaging import MAX_MESSAGE_LENGTH
from app.storage import MemoryStore
from api.server import _make_app

TOPIC = "universal-connectivity"


def _message(text, *, timestamp):
    return {
        "message": text,
        "topic": TOPIC,
        "sender_id": "peer-remote",
        "sender_nick": "Remote",
        "timestamp": timestamp,
        "read": False,
    }


class _FakeEngine:
    """Duck-typed engine: no libp2p host, real service wiring."""

    def __init__(self):
        self.ready = True
        self.running = True
        self.failed = False
        self.stop_event = threading.Event()
        self.nickname = "adapter-test"
        self.port = 45123
        self.topic = None
        self.strict_signing = True
        self.download_dir = "/tmp"
        self.transport_addrs = ["/ip4/127.0.0.1/tcp/45123"]
        self.full_multiaddrs = [
            "/ip4/127.0.0.1/tcp/45123/p2p/peer-adapter"
        ]
        self.connect_addrs = []
        self.connected_peers = set()
        self.message_store = MemoryStore()
        self.sent: list[tuple[str, str]] = []
        self.dialed: list[str] = []
        self.host = type("FakeHost", (), {"get_id": lambda s: "peer-adapter"})()
        self.outgoing_queue = SimpleNamespace(sync_q=queue.Queue())
        self.peer_connection_queue = SimpleNamespace(sync_q=queue.Queue())
        self.chat_room = type(
            "FakeChatRoom",
            (),
            {
                "get_subscribed_topics": lambda s: {TOPIC},
                "get_all_subscriptions": lambda s: {TOPIC},
                "get_connected_peers": lambda s: set(),
                "get_peer_count": lambda s: 0,
            },
        )()

    async def start(self):
        self.ready = True
        self.running = True

    def request_stop(self):
        self.stop_event.set()

    def send_message(self, text):
        self.sent.append(("default", text))
        return True

    def send_message_to_topic(self, topic, text):
        self.sent.append((topic, text))
        return True

    def connect_to_peer(self, multiaddr):
        self.dialed.append(multiaddr)
        return True

    def get_subscribed_topics(self):
        return {TOPIC}

    def get_connection_info(self):
        return {
            "peer_id": "peer-adapter",
            "nickname": self.nickname,
            "multiaddr": self.full_multiaddrs[0],
            "multiaddrs": list(self.full_multiaddrs),
            "listen_addrs": list(self.transport_addrs),
            "connected_peers": set(self.connected_peers),
            "peer_count": len(self.connected_peers),
        }


class AdapterEquivalenceTests(AsyncHTTPTestCase):
    def get_app(self):
        self.engine = _FakeEngine()
        self.runtime = ApplicationRuntime(service=self.engine)
        return _make_app(self.runtime)

    def _json(self, response):
        return json.loads(response.body)

    def _post(self, path, payload):
        return self.fetch(
            path,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload),
        )

    def test_publish_message_has_the_same_domain_effect(self):
        self.runtime.messaging.send("  direct  ")
        response = self._post("/api/v1/messages", {"message": "  http  "})

        self.assertEqual(response.code, 202)
        self.assertTrue(self._json(response)["success"])
        queued1 = self.engine.outgoing_queue.sync_q.get_nowait()["message"]
        queued2 = self.engine.outgoing_queue.sync_q.get_nowait()["message"]
        self.assertEqual([queued1, queued2], ["direct", "http"])

    def test_publish_to_topic_matches_direct_service(self):
        self.runtime.messaging.send_to_topic(TOPIC, "direct-topic")
        response = self._post(f"/api/v1/messages/{TOPIC}", {"message": "http-topic"})

        self.assertEqual(response.code, 202)
        queued1 = self.engine.outgoing_queue.sync_q.get_nowait()["message"]
        queued2 = self.engine.outgoing_queue.sync_q.get_nowait()["message"]
        self.assertEqual([queued1, queued2], ["direct-topic", "http-topic"])

    def test_history_response_matches_the_service_envelope(self):
        for index in range(3):
            self.engine.message_store.messages.append(
                _message(f"m{index}", timestamp=float(index))
            )

        direct = self.runtime.storage.history(TOPIC, limit=2, offset=1)
        response = self.fetch(f"/api/v1/messages/{TOPIC}?limit=2&offset=1")

        self.assertEqual(response.code, 200)
        self.assertEqual(self._json(response)["data"], direct)

    def test_status_response_matches_direct_status(self):
        direct = self.runtime.status()
        response = self.fetch("/api/v1/service/status")

        self.assertEqual(response.code, 200)
        data = self._json(response)["data"]
        for field in (
            "state",
            "ready",
            "running",
            "failed",
            "peer_count",
            "peer_id",
            "nickname",
        ):
            self.assertEqual(data[field], getattr(direct, field), field)

    def test_connect_matches_direct_service(self):
        key_pair = create_new_key_pair(b"adapter-equivalence".ljust(32, b"0"))
        target = (
            f"/ip4/127.0.0.1/tcp/4001/p2p/{ID.from_pubkey(key_pair.public_key)}"
        )

        direct = self.runtime.connections.connect(target)
        response = self._post("/api/v1/peers/connect", {"multiaddr": target})

        self.assertEqual(response.code, 202)
        self.assertEqual(self._json(response)["data"], direct)
        q1 = self.engine.peer_connection_queue.sync_q.get_nowait()
        q2 = self.engine.peer_connection_queue.sync_q.get_nowait()
        self.assertEqual([q1, q2], [target, target])

    def test_validation_errors_have_the_same_boundary(self):
        with self.assertRaises(ValidationError):
            self.runtime.messaging.send("   ")
        blank = self._post("/api/v1/messages", {"message": "   "})
        self.assertEqual(blank.code, 400)

        oversized = "x" * (MAX_MESSAGE_LENGTH + 1)
        with self.assertRaises(ValidationError):
            self.runtime.messaging.send(oversized)
        too_long = self._post("/api/v1/messages", {"message": oversized})
        self.assertEqual(too_long.code, 400)
        self.assertIn("4096", self._json(too_long)["error"]["message"])

    def test_invalid_multiaddr_is_rejected_by_both_adapters(self):
        with self.assertRaises(ValidationError):
            self.runtime.connections.connect("not-a-multiaddr")
        response = self._post(
            "/api/v1/peers/connect", {"multiaddr": "not-a-multiaddr"}
        )
        self.assertEqual(response.code, 400)
        self.assertEqual(self.engine.dialed, [])


if __name__ == "__main__":
    unittest.main()
