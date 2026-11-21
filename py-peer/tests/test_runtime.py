"""Tests for the shared runtime, event bus, and single-instance wiring."""

import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import trio

import core.headless as headless_module
from app import ApplicationRuntime, DataDirectoryError, RuntimeConfig
from app.events import Event, EventBus, EventType
from api.base import as_runtime


class _ReadyService:
    """Duck-typed engine double (no host, no UI)."""

    def __init__(self):
        self.ready = False
        self.running = False
        self.failed = False
        self.stop_event = threading.Event()
        self.nickname = "fake"
        self.port = 41234
        self.topic = None
        self.strict_signing = True
        self.download_dir = "/tmp"
        self.transport_addrs = []
        self.full_multiaddrs = []
        self.connect_addrs = []

    async def start(self):
        self.ready = True
        self.running = True

    def request_stop(self):
        self.stop_event.set()

    def get_connection_info(self):
        return {
            "peer_id": "peer-fake",
            "nickname": self.nickname,
            "multiaddr": None,
            "multiaddrs": [],
            "listen_addrs": [],
            "connected_peers": set(),
            "peer_count": 0,
        }


class _FailingService(_ReadyService):
    async def start(self):
        self.failed = True
        raise RuntimeError("simulated startup failure")


class EventBusTests(unittest.TestCase):
    def test_type_filter(self):
        bus = EventBus()
        subscription = bus.subscribe([EventType.SYSTEM])
        bus.publish(Event(EventType.MESSAGE_RECEIVED, {"message": "hi"}))
        self.assertIsNone(subscription.get_nowait())
        bus.publish(Event(EventType.SYSTEM, {"message": "system"}))
        event = subscription.get_nowait()
        self.assertEqual(event.type, EventType.SYSTEM)

    def test_full_queue_drops_oldest_instead_of_blocking(self):
        bus = EventBus(maxsize=2)
        subscription = bus.subscribe()
        for index in range(3):
            bus.publish(Event(EventType.SYSTEM, {"index": index}))
        self.assertEqual(subscription.get_nowait().data["index"], 1)
        self.assertEqual(subscription.get_nowait().data["index"], 2)
        self.assertEqual(subscription.dropped, 1)

    def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        subscription = bus.subscribe()
        bus.unsubscribe(subscription)
        bus.publish(Event(EventType.SYSTEM, {"index": 1}))
        self.assertTrue(subscription.closed)
        self.assertIsNone(subscription.get_nowait())

    def test_publish_never_blocks_with_no_consumer(self):
        bus = EventBus(maxsize=1)
        bus.subscribe()
        started = time.monotonic()
        for index in range(1000):
            bus.publish(Event(EventType.MESSAGE_RECEIVED, {"index": index}))
        self.assertLess(time.monotonic() - started, 1.0)


class RuntimeTests(unittest.TestCase):
    def test_services_share_one_engine_and_event_bus(self):
        service = _ReadyService()
        runtime = ApplicationRuntime(service=service)
        self.assertIs(runtime.service, service)
        self.assertIs(service.event_bus, runtime.events)
        self.assertIs(runtime.messaging.engine, service)
        self.assertIs(runtime.peer.engine, service)

    def test_status_reports_engine_state(self):
        runtime = ApplicationRuntime(service=_ReadyService())
        status = runtime.status()
        self.assertEqual(status.nickname, "fake")
        self.assertEqual(status.port, 41234)
        self.assertEqual(status.state, "created")

    def test_start_twice_raises(self):
        runtime = ApplicationRuntime(service=_ReadyService())
        trio.run(runtime.start)
        with self.assertRaisesRegex(RuntimeError, "already been called"):
            trio.run(runtime.start)

    def test_start_in_thread_reaches_ready(self):
        runtime = ApplicationRuntime(service=_ReadyService())
        runtime.start_in_thread(timeout=5)
        self.assertTrue(runtime.ready)
        self.assertTrue(runtime.join(5))
        runtime.close()

    def test_startup_failure_cleans_up_and_closes_subscribers(self):
        service = _FailingService()
        runtime = ApplicationRuntime(service=service)
        subscription = runtime.subscribe()
        with self.assertRaisesRegex(RuntimeError, "failed to start"):
            runtime.start_in_thread(timeout=5)
        self.assertTrue(runtime.failed)
        self.assertTrue(subscription.closed)
        self.assertTrue(runtime.join(5))

    def test_as_runtime_reuses_one_runtime_for_a_bare_service(self):
        service = _ReadyService()
        first = as_runtime(service)
        second = as_runtime(service)
        self.assertIs(first, second)
        self.assertIs(first.service, service)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RealRuntimeLifecycleTests(unittest.TestCase):
    """End-to-end runtime lifecycle with a real libp2p host (no bootstrap)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._previous_bootstrap = headless_module.BOOTSTRAP_PEERS
        headless_module.BOOTSTRAP_PEERS = []

    def tearDown(self):
        headless_module.BOOTSTRAP_PEERS = self._previous_bootstrap
        self._tmp.cleanup()

    def _runtime(self, port: int) -> ApplicationRuntime:
        return ApplicationRuntime(
            RuntimeConfig(
                nickname="lifecycle",
                port=port,
                data_dir=self._tmp.name,
                announce_host="127.0.0.1",
                connect_addrs=[],
            )
        )

    def _assert_port_released(self, port: int):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))

    def test_repeated_start_stop_cycles_release_listeners_threads_and_identity(self):
        baseline_threads = {
            thread.ident for thread in threading.enumerate() if thread.is_alive()
        }
        peer_ids = set()

        for _ in range(3):
            port = _free_port()
            runtime = self._runtime(port)
            runtime.start_in_thread(timeout=30)
            try:
                self.assertTrue(runtime.ready)
                self.assertTrue(runtime.running)
                self.assertIsNotNone(runtime.service.host)
                # Every in-process adapter resolves to the same engine/service.
                self.assertIs(runtime.messaging.engine, runtime.service)
                self.assertIs(runtime.storage.engine, runtime.service)
                self.assertIs(runtime.peer.engine, runtime.service)

                status = runtime.status()
                self.assertTrue(status.ready)
                self.assertTrue(status.running)
                self.assertFalse(status.failed)
                self.assertTrue(
                    any(f"/tcp/{port}" in addr for addr in status.listen_addrs),
                    status.listen_addrs,
                )
                peer_ids.add(status.peer_id)
            finally:
                runtime.request_stop()
                self.assertTrue(runtime.join(20), "runtime thread did not stop")
                runtime.close()

            self._assert_port_released(port)

        # Same data directory: one persisted identity across all three cycles.
        self.assertEqual(len(peer_ids), 1, peer_ids)
        # No runtime threads or other thread-shaped leftovers accumulate.
        remaining = {
            thread.ident
            for thread in threading.enumerate()
            if thread.is_alive() and thread.ident not in baseline_threads
        }
        leaked = [
            thread.name
            for thread in threading.enumerate()
            if thread.is_alive() and thread.ident in remaining
        ]
        self.assertEqual(leaked, [])

    def test_exactly_one_host_is_created_per_start(self):
        created = []
        real_new_host = headless_module.new_host

        def counting_new_host(*args, **kwargs):
            created.append(1)
            return real_new_host(*args, **kwargs)

        runtime = self._runtime(_free_port())
        with patch.object(headless_module, "new_host", counting_new_host):
            runtime.start_in_thread(timeout=30)
            try:
                self.assertEqual(len(created), 1)
            finally:
                runtime.request_stop()
                self.assertTrue(runtime.join(20))

    def test_identity_and_history_survive_a_real_restart(self):
        topic = "universal-connectivity"

        first = self._runtime(_free_port())
        first.start_in_thread(timeout=30)
        try:
            peer_id = first.status().peer_id
            self.assertTrue(
                first.store.append(
                    {
                        "message": "persisted through the runtime",
                        "topic": topic,
                        "sender_id": peer_id,
                        "sender_nick": "lifecycle",
                        "timestamp": time.time(),
                    }
                )
            )
        finally:
            first.request_stop()
            self.assertTrue(first.join(20))

        second = self._runtime(_free_port())
        second.start_in_thread(timeout=30)
        try:
            self.assertEqual(second.status().peer_id, peer_id)
            page = second.storage.history(topic, limit=10)
            self.assertEqual(page["total"], 1)
            self.assertEqual(
                page["messages"][0]["message"], "persisted through the runtime"
            )
        finally:
            second.request_stop()
            self.assertTrue(second.join(20))

    def test_invalid_listen_transport_fails_startup_and_cleans_up(self):
        runtime = ApplicationRuntime(
            RuntimeConfig(
                nickname="bad-listen",
                port=_free_port(),
                data_dir=self._tmp.name,
                announce_host="127.0.0.1",
                listen_addrs=["/ip4/127.0.0.1/udp/4001"],
            )
        )

        with self.assertRaisesRegex(RuntimeError, "failed to start"):
            runtime.start_in_thread(timeout=20)

        self.assertTrue(runtime.failed)
        self.assertTrue(runtime.join(10))
        self.assertTrue(runtime.service._shutdown_done)

    def test_unwritable_data_directory_is_rejected_before_start(self):
        import os
        import stat

        if os.geteuid() == 0:  # pragma: no cover - root bypasses permissions
            self.skipTest("running as root; permission bits are not enforced")
        locked = os.path.join(self._tmp.name, "locked")
        os.makedirs(locked)
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        try:
            with self.assertRaises(DataDirectoryError) as raised:
                ApplicationRuntime(
                    RuntimeConfig(nickname="locked", data_dir=locked)
                )
            self.assertIn("not writable", str(raised.exception))
        finally:
            os.chmod(locked, stat.S_IRWXU)


if __name__ == "__main__":
    unittest.main()
