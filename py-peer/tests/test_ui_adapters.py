"""Adapter tests: Textual UI and simple CLI consume the runtime event bus."""

import asyncio
import io
import queue
import threading
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from app import ApplicationRuntime
from app.events import Event, EventType
from main import _print_runtime_event
from ui.textual import ChatUI


class _ReadyService:
    """Duck-typed engine double (no host, no UI)."""

    def __init__(self):
        self.ready = True
        self.running = True
        self.failed = False
        self.stop_event = threading.Event()
        self.nickname = "fake"
        self.port = 41234
        self.topic = None
        self.strict_signing = True
        self.download_dir = "/tmp"
        self.transport_addrs = ["/ip4/127.0.0.1/tcp/41234"]
        self.full_multiaddrs = ["/ip4/127.0.0.1/tcp/41234/p2p/peer-fake"]
        self.connect_addrs = []
        self.outgoing_queue = SimpleNamespace(sync_q=queue.Queue())

    async def start(self):
        self.ready = True
        self.running = True

    def request_stop(self):
        self.stop_event.set()

    def get_connection_info(self):
        return {
            "peer_id": "peer-fake",
            "nickname": self.nickname,
            "multiaddr": self.full_multiaddrs[0],
            "multiaddrs": list(self.full_multiaddrs),
            "listen_addrs": list(self.transport_addrs),
            "connected_peers": set(),
            "peer_count": 0,
        }


class _FakeLog:
    def __init__(self):
        self.lines = []

    def write_line(self, line):
        self.lines.append(line)

    def clear(self):
        self.lines.clear()


class TextualAdapterTests(unittest.TestCase):
    def setUp(self):
        self.runtime = ApplicationRuntime(service=_ReadyService())
        self.ui = ChatUI(runtime=self.runtime)
        self.chat_log = _FakeLog()
        self.system_log = _FakeLog()
        self.peers_log = _FakeLog()
        self.ui.chat_log = self.chat_log
        self.ui.system_log = self.system_log
        self.ui.peers_log = self.peers_log
        self.ui.running = True

    def tearDown(self):
        self.ui.on_unmount()
        self.runtime.close()

    def test_ui_subscribes_to_event_bus_and_unsubscribes(self):
        self.assertIsNotNone(self.ui._subscription)
        self.assertEqual(self.runtime.events.subscriber_count, 1)
        self.ui.on_unmount()
        self.assertIsNone(self.ui._subscription)
        self.assertEqual(self.runtime.events.subscriber_count, 0)

    def test_message_and_system_events_reach_widgets(self):
        self.runtime.publish(Event(EventType.MESSAGE_RECEIVED, {
            "type": "chat_message",
            "message": "hello",
            "sender_nick": "alice",
            "sender_id": "peer-alice",
            "topic": "universal-connectivity",
        }))
        self.runtime.publish(Event(EventType.SYSTEM, {
            "type": "system_message",
            "message": "connected",
        }))
        self.ui._drain_events()

        self.assertEqual(len(self.chat_log.lines), 1)
        self.assertIn("alice", self.chat_log.lines[0])
        self.assertIn("hello", self.chat_log.lines[0])
        self.assertTrue(any("connected" in line for line in self.system_log.lines))

    def test_file_message_is_reported_as_system_note(self):
        self.runtime.publish(Event(EventType.MESSAGE_RECEIVED, {
            "type": "file_message",
            "sender_nick": "bob",
            "file_name": "notes.txt",
            "topic": "universal-connectivity",
        }))
        self.ui._drain_events()
        self.assertEqual(self.chat_log.lines, [])
        self.assertTrue(any("notes.txt" in line for line in self.system_log.lines))

    def test_peer_events_trigger_refresh(self):
        self.runtime.publish(Event(EventType.PEER_CONNECTED, {"peer_id": "peer-alice"}))
        self.ui._drain_events()
        self.assertTrue(any("Peer connected" in line for line in self.system_log.lines))
        self.assertTrue(any("Connected: 0" in line for line in self.peers_log.lines))

    def test_submitted_input_goes_through_the_messaging_service(self):
        class _Input:
            cleared = False

            def clear(self):
                self.cleared = True

        message_input = _Input()
        self.ui.message_input = message_input

        asyncio.run(
            self.ui.on_input_submitted(SimpleNamespace(value="  hello from ui  "))
        )

        self.assertTrue(message_input.cleared)
        queued = self.runtime.service.outgoing_queue.sync_q.get_nowait()
        self.assertEqual(queued["message"], "hello from ui")


class SimpleCliAdapterTests(unittest.TestCase):
    def test_reexported_from_main(self):
        from ui.interactive import _print_runtime_event as direct_fn
        self.assertIs(_print_runtime_event, direct_fn)

    def test_chat_event_is_printed(self):
        event = Event(EventType.MESSAGE_RECEIVED, {
            "type": "chat_message",
            "message": "hello",
            "sender_nick": "alice",
            "sender_id": "peer-alice-123456",
        })
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            _print_runtime_event(event)
        self.assertIn("alice(peer-ali)", buffer.getvalue())
        self.assertIn("hello", buffer.getvalue())

    def test_system_event_is_printed(self):
        event = Event(EventType.SYSTEM, {
            "type": "system_message",
            "message": "subscribed",
        })
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            _print_runtime_event(event)
        self.assertIn("subscribed", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
