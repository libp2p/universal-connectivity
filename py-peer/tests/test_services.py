"""Contract tests for the framework-independent application service layer."""

import os
import tempfile
import unittest

from app.errors import ConflictError, NotFoundError, NotReadyError, ValidationError
from app.storage import MemoryStore
from app.services import (
    DiscoveryService,
    FileService,
    IdentityService,
    MessagingService,
    PeerService,
    StorageService,
)
from app.chatroom import PUBSUB_DISCOVERY_TOPIC


class _FakeHost:
    def get_id(self):
        return "peer-local"


import queue as _queue
from types import SimpleNamespace


class _FakeChatRoom:
    """Minimal ChatRoom double for service tests."""

    def __init__(self, subscribed):
        self._subscribed = set(subscribed)
        self._peers: set[str] = set()

    def get_subscribed_topics(self):
        return set(self._subscribed)

    def get_all_subscriptions(self):
        return set(self._subscribed)

    def get_connected_peers(self):
        return set(self._peers)

    def get_peer_count(self):
        return len(self._peers)

    def subscribe_to_topic(self, topic):
        self._subscribed.add(topic)
        return True


class _FakeEngine:
    """Minimal engine double: services must not need a real libp2p host."""

    port = 4001
    topic = None
    strict_signing = True
    transport_addrs = ["/ip4/127.0.0.1/tcp/4001"]
    full_multiaddrs = ["/ip4/127.0.0.1/tcp/4001/p2p/peer-local"]
    connect_addrs = []

    def __init__(self, ready=True):
        self.ready = ready
        self.running = ready  # services check engine.running
        self.nickname = "tester"
        self.download_dir = tempfile.mkdtemp()
        self.host = _FakeHost()
        self.connected_peers = set()
        self.sent = []
        self.subscribed = {"universal-connectivity"}
        self.message_store = MemoryStore()
        # chat_room needed by MessagingService / DiscoveryService guards
        self.chat_room = _FakeChatRoom(self.subscribed) if ready else None
        # outgoing_queue needed by MessagingService.enqueue
        # The service calls queue.sync_q.put_nowait(), mirroring janus.Queue API
        if ready:
            _q: _queue.Queue[dict] = _queue.Queue()
            self.outgoing_queue = SimpleNamespace(sync_q=_q)
            _fq: _queue.Queue[dict] = _queue.Queue()
            self.file_share_queue = SimpleNamespace(sync_q=_fq)
            _tq: _queue.Queue[dict] = _queue.Queue()
            self.topic_subscription_queue = SimpleNamespace(sync_q=_tq)
        else:
            self.outgoing_queue = None
            self.file_share_queue = None
            self.topic_subscription_queue = None
        for index in range(5):
            self.message_store.append(
                {
                    "message": f"m{index}",
                    "sender_id": "peer-remote",
                    "sender_nick": "Remote",
                    "topic": "universal-connectivity",
                    "timestamp": 1000.0 + index,
                }
            )

    # --- state ---------------------------------------------------------
    def get_connection_info(self):
        return {
            "peer_id": "peer-local",
            "nickname": self.nickname,
            "multiaddr": self.full_multiaddrs[0],
            "multiaddrs": list(self.full_multiaddrs),
            "listen_addrs": list(self.transport_addrs),
            "connected_peers": set(self.connected_peers),
            "peer_count": len(self.connected_peers),
        }

    def get_subscribed_topics(self):
        return set(self.subscribed)

    def get_all_topics_with_info(self):
        return {topic: {"unread": 0} for topic in self.subscribed}

    def get_topic_messages(self, topic):
        return [{"message": f"m{index}"} for index in range(5)]

    def get_unread_count(self, topic):
        return 0

    def mark_topic_as_read(self, topic):
        pass

    # --- operations ----------------------------------------------------
    def send_message(self, text):
        self.sent.append(text)
        return True

    def send_message_to_topic(self, topic, text):
        self.sent.append((topic, text))
        return True

    def subscribe_to_topic(self, topic):
        self.subscribed.add(topic)
        return True

    def share_file(self, path, topic):
        self.sent.append(("share", path, topic))
        return True

    def download_file(self, cid, name):
        return True

    def get_shared_files(self):
        return []

    def get_shared_file(self, cid):
        return None

    # --- identity ------------------------------------------------------
    def get_peer_info_cache_snapshot(self):
        return {}

    def get_peer_info(self, peer_id):
        return None

    def get_public_key_for_peer(self, peer_id):
        return None

    def delete_peer_info(self, peer_id):
        return False


class PeerServiceTests(unittest.TestCase):
    def test_connection_summary_matches_engine_state(self):
        engine = _FakeEngine()
        summary = PeerService(engine).connection_info()
        self.assertEqual(summary.peer_id, "peer-local")
        self.assertEqual(summary.peer_count, 0)
        self.assertEqual(summary.listen_addrs, ["/ip4/127.0.0.1/tcp/4001"])

    def test_invalid_peer_id_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            PeerService(_FakeEngine()).peer_detail("!!!")


class MessagingServiceTests(unittest.TestCase):
    def test_send_queues_through_engine(self):
        engine = _FakeEngine()
        MessagingService(engine, StorageService(engine)).send("  hello  ")
        queued = engine.outgoing_queue.sync_q.get_nowait()
        self.assertEqual(queued["message"], "hello")

    def test_blank_message_is_rejected(self):
        engine = _FakeEngine()
        with self.assertRaises(ValidationError):
            MessagingService(engine, StorageService(engine)).send("   ")

    def test_send_before_ready_raises_not_ready(self):
        engine = _FakeEngine(ready=False)
        with self.assertRaises(NotReadyError):
            MessagingService(engine, StorageService(engine)).send("hi")

    def test_unsubscribed_topic_is_rejected(self):
        engine = _FakeEngine()
        with self.assertRaises(ValidationError):
            MessagingService(engine, StorageService(engine)).send_to_topic(
                "missing-topic", "hi"
            )


class StorageServiceTests(unittest.TestCase):
    def test_history_paginates(self):
        engine = _FakeEngine()
        page = StorageService(engine).history("universal-connectivity", limit=2, offset=1)
        self.assertEqual(page["total"], 5)
        self.assertEqual([m["message"] for m in page["messages"]], ["m1", "m2"])

    def test_history_limit_is_validated(self):
        with self.assertRaises(ValidationError):
            StorageService(_FakeEngine()).history("universal-connectivity", limit=0)


class DiscoveryServiceTests(unittest.TestCase):
    def test_duplicate_subscription_conflicts(self):
        with self.assertRaises(ConflictError):
            DiscoveryService(_FakeEngine()).subscribe("universal-connectivity")

    def test_reserved_discovery_topic_is_rejected(self):
        with self.assertRaises(ValidationError):
            DiscoveryService(_FakeEngine()).subscribe(PUBSUB_DISCOVERY_TOPIC)

    def test_subscribe_before_ready_raises_not_ready(self):
        with self.assertRaises(NotReadyError):
            DiscoveryService(_FakeEngine(ready=False)).subscribe("new-topic")

    def test_unknown_topic_info_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            DiscoveryService(_FakeEngine()).topic_info("missing")


class FileServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = _FakeEngine()
        self.service = FileService(self.engine)

    def test_share_rejects_files_outside_download_dir(self):
        handle, path = tempfile.mkstemp()
        os.close(handle)
        try:
            with self.assertRaises(ValidationError):
                self.service.share_local_file(path, "universal-connectivity")
        finally:
            os.unlink(path)

    def test_share_inside_download_dir_is_queued(self):
        path = os.path.join(self.engine.download_dir, "inside.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("data")
        result = self.service.share_local_file(path, "universal-connectivity")
        self.assertEqual(result["filename"], "inside.txt")

    def test_upload_strips_path_components_and_avoids_overwrite(self):
        first = self.service.store_upload("../../evil.txt", b"one")
        second = self.service.store_upload("../../evil.txt", b"two")
        self.assertEqual(os.path.dirname(first["path"]), self.engine.download_dir)
        self.assertEqual(first["filename"], "evil.txt")
        self.assertEqual(second["filename"], "evil_1.txt")
        self.assertEqual(second["size"], 3)

    def test_upload_before_ready_raises_not_ready(self):
        with self.assertRaises(NotReadyError):
            FileService(_FakeEngine(ready=False)).store_upload("a.txt", b"x")


class IdentityServiceTests(unittest.TestCase):
    def test_missing_identify_cache_entry_is_not_found(self):
        with self.assertRaises(NotFoundError):
            IdentityService(_FakeEngine()).get("peer-unknown")

    def test_missing_public_key_is_not_found(self):
        with self.assertRaises(NotFoundError):
            IdentityService(_FakeEngine()).public_key_hex("peer-unknown")


if __name__ == "__main__":
    unittest.main()
