"""Regression tests for discovery-topic filtering and snapshot helpers."""

import unittest
from types import SimpleNamespace

from app.chatroom import (
    CHAT_TOPIC,
    PUBSUB_DISCOVERY_TOPIC,
    ChatRoom,
    _snapshot_keys,
)


class TopicFilteringTests(unittest.TestCase):
    def _room(self):
        room = object.__new__(ChatRoom)
        room.subscriptions = {
            CHAT_TOPIC: object(),
            PUBSUB_DISCOVERY_TOPIC: object(),
        }
        return room

    def test_discovery_topic_is_not_a_chat_topic(self):
        self.assertEqual(self._room().get_subscribed_topics(), {CHAT_TOPIC})

    def test_all_subscriptions_keep_protocol_topic(self):
        self.assertEqual(
            self._room().get_all_subscriptions(),
            {CHAT_TOPIC, PUBSUB_DISCOVERY_TOPIC},
        )

    def test_connected_peers_snapshot(self):
        room = object.__new__(ChatRoom)
        room.pubsub = SimpleNamespace(
            peers={"peer-a": object(), "peer-b": object()}
        )
        self.assertEqual(room.get_connected_peers(), {"peer-a", "peer-b"})

    def test_snapshot_retries_if_dict_changes_during_copy(self):
        class FlakyMapping:
            def __init__(self):
                self.calls = 0

            def keys(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("dictionary changed size during iteration")
                return ["topic-a"]

        self.assertEqual(_snapshot_keys(FlakyMapping()), ["topic-a"])


if __name__ == "__main__":
    unittest.main()
