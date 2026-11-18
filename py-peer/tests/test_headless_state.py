"""Regression tests for bounded history, legacy queues, and API snapshots."""

import asyncio
import queue
import time
import unittest
from unittest.mock import patch

from app.chatroom import ChatMessage
from core.headless import HeadlessService


class _FakeJanusQueue:
    """Only the thread-safe side used by HeadlessService._put_legacy."""

    def __init__(self, maxsize=0):
        self.sync_q = queue.Queue(maxsize=maxsize)


class _FakeChatRoom:
    def get_subscribed_topics(self):
        return {"topic-x"}


class HeadlessStateTests(unittest.TestCase):
    def setUp(self):
        self.service = HeadlessService(nickname="test", ui_mode=True)
        self.service.message_queue = _FakeJanusQueue()
        self.service.system_queue = _FakeJanusQueue()
        self.service.host = None
        self.service.running = True
        self.service.chat_room = None

    def _handle(self, text):
        message = ChatMessage(
            message=text,
            sender_id="peer-x",
            sender_nick="X",
            topic="topic-x",
        )
        asyncio.run(self.service._handle_chat_message(message))

    def test_history_is_capped_and_unread_count_follows_trim(self):
        with patch("app.services.storage.MAX_TOPIC_MESSAGES", 3):
            for i in range(5):
                self._handle(f"m{i}")

            messages = self.service.get_topic_messages("topic-x")
            self.assertEqual([m["message"] for m in messages], ["m2", "m3", "m4"])
            self.assertEqual(self.service.get_unread_count("topic-x"), 3)

    def test_get_topic_messages_returns_a_copy(self):
        self._handle("one")
        copied = self.service.get_topic_messages("topic-x")
        copied.clear()
        self.assertEqual(len(self.service.get_topic_messages("topic-x")), 1)

    def test_mark_read_resets_unread(self):
        self._handle("one")
        self._handle("two")
        self.service.mark_topic_as_read("topic-x")
        self.assertEqual(self.service.get_unread_count("topic-x"), 0)
        self.assertTrue(
            all(m["read"] for m in self.service.get_topic_messages("topic-x"))
        )

    def test_topics_info_uses_snapshot_and_copy(self):
        with patch("app.services.storage.MAX_TOPIC_MESSAGES", 10):
            self._handle("one")
            self._handle("two")
        self.service.chat_room = _FakeChatRoom()
        info = self.service.get_all_topics_with_info()
        self.assertEqual(info["topic-x"]["total_count"], 2)
        self.assertEqual(info["topic-x"]["last_message"]["message"], "two")

    def test_legacy_queue_is_bounded(self):
        bounded = _FakeJanusQueue(maxsize=1)
        self.service._put_legacy(bounded, {"n": 1})
        self.service._put_legacy(bounded, {"n": 2})
        self.assertEqual(bounded.sync_q.qsize(), 1)

    def test_system_message_timestamp_is_wall_clock(self):
        before = time.time()
        asyncio.run(self.service._send_system_message("hello"))
        payload = self.service.system_queue.sync_q.get_nowait()
        self.assertGreaterEqual(payload["timestamp"], before)
        self.assertLess(payload["timestamp"], time.time() + 1)

    def test_shared_file_api_metadata_hides_local_path(self):
        with self.service._state_lock:
            self.service.shared_files["cid"] = {
                "filename": "f.txt",
                "filesize": 3,
                "filepath": "/private/secret/f.txt",
            }
        self.assertEqual(
            self.service.get_shared_files(),
            [{"cid": "cid", "filename": "f.txt", "filesize": 3}],
        )
        self.assertEqual(
            self.service.get_shared_file("cid"),
            {"cid": "cid", "filename": "f.txt", "filesize": 3},
        )

    def test_peer_cache_snapshot_and_delete(self):
        with self.service._state_lock:
            self.service.peer_info_cache["peer-x"] = {
                "public_key": b"key",
                "timestamp": time.time(),
            }
        snapshot = self.service.get_peer_info_cache_snapshot()
        self.assertEqual(snapshot["peer-x"]["public_key"], b"key")
        # Mutating the snapshot must not mutate the live cache.
        snapshot["peer-x"]["public_key"] = b"other"
        self.assertEqual(
            self.service.get_peer_info("peer-x")["public_key"], b"key"
        )
        self.assertTrue(self.service.delete_peer_info("peer-x"))
        self.assertFalse(self.service.delete_peer_info("peer-x"))


if __name__ == "__main__":
    unittest.main()
