"""Regression tests for service startup and shutdown lifecycle."""

import signal
import socket
import threading
import time
import unittest

import trio
from libp2p.host.exceptions import StreamFailure

import core.headless as headless_module
from core.headless import HeadlessService
from main import install_shutdown_signal_handlers, restore_signal_handlers


class _FailingService(HeadlessService):
    async def _run_service(self):
        raise StreamFailure("simulated core protocol failure")


class _NoopService(HeadlessService):
    async def _run_service(self):
        self.ready = True
        self.running = True


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LifecycleTests(unittest.TestCase):
    def test_core_protocol_failure_is_not_swallowed(self):
        service = _FailingService(nickname="test", ui_mode=True)
        # trio_asyncio wraps the body exception in an ExceptionGroup; the
        # important behavior is that it propagates at all (the old code
        # swallowed it) and that the service is marked failed.
        with self.assertRaises((BaseExceptionGroup, StreamFailure)):
            trio.run(service.start)
        self.assertTrue(service.failed)
        self.assertFalse(service.ready)
        self.assertTrue(service._shutdown_done)

    def test_request_stop_is_idempotent_and_does_not_need_a_host(self):
        service = HeadlessService(nickname="test", ui_mode=True)
        self.assertFalse(service.stop_event.is_set())
        service.request_stop()
        service.request_stop()
        self.assertTrue(service.stop_event.is_set())
        self.assertIsNone(service.chat_room)

    def test_start_twice_raises(self):
        service = _NoopService(nickname="test", ui_mode=True)
        trio.run(service.start)
        with self.assertRaisesRegex(RuntimeError, "already been called"):
            trio.run(service.start)

    def test_sigterm_handler_requests_stop(self):
        class _Recorder:
            def __init__(self):
                self.calls = 0

            def request_stop(self):
                self.calls += 1

        recorder = _Recorder()
        previous = install_shutdown_signal_handlers(recorder)
        try:
            if signal.SIGTERM not in previous:
                self.skipTest("SIGTERM handlers are unavailable on this platform")
            # Invoke the installed handler directly instead of signalling the
            # whole test process.
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        finally:
            restore_signal_handlers(previous)
        self.assertEqual(recorder.calls, 1)


class ShutdownIntegrationTests(unittest.TestCase):
    def test_request_stop_from_another_thread_tears_down(self):
        original_bootstrap = headless_module.BOOTSTRAP_PEERS
        headless_module.BOOTSTRAP_PEERS = []
        port = _free_port()
        service = HeadlessService(
            nickname="test-shutdown",
            port=port,
            seed=f"test-shutdown-{time.time_ns()}",
            ui_mode=True,
            listen_addrs=[f"/ip4/127.0.0.1/tcp/{port}"],
        )
        service_thread = threading.Thread(
            target=lambda: trio.run(service.start), daemon=True
        )
        try:
            service_thread.start()
            deadline = time.monotonic() + 20
            while not service.ready and time.monotonic() < deadline:
                if service.failed:
                    break
                time.sleep(0.05)
            self.assertTrue(service.ready, "service never became ready")

            # This is the call the UI teardown, signal handler, and Tornado
            # stop endpoint now use.
            service.request_stop()
            service_thread.join(20)

            self.assertFalse(service_thread.is_alive(), "trio thread did not exit")
            self.assertFalse(service.ready)
            self.assertFalse(service.running)
            self.assertTrue(service._shutdown_done)
            self.assertTrue(service.message_queue.closed)
            self.assertTrue(service.outgoing_queue.closed)
        finally:
            service.request_stop()
            service_thread.join(5)
            headless_module.BOOTSTRAP_PEERS = original_bootstrap


if __name__ == "__main__":
    unittest.main()
