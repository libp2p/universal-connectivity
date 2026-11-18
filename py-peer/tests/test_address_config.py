"""Transport/address configuration and announced-address correctness."""

import socket
import threading
import time
import unittest

import multiaddr
import trio

import core.headless as headless_module
from core.headless import HeadlessService


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_service(service):
    thread = threading.Thread(target=lambda: trio.run(service.start), daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not service.ready and not service.failed and time.monotonic() < deadline:
        time.sleep(0.05)
    return thread


class ResolveListenAddrsTests(unittest.TestCase):
    def test_default_is_wildcard_tcp_on_port(self):
        service = HeadlessService(nickname="t", port=45678, ui_mode=True)
        addrs = service._resolve_listen_addrs()
        self.assertIn("/ip4/0.0.0.0/tcp/45678", [str(addr) for addr in addrs])

    def test_custom_listen_addrs_are_parsed(self):
        service = HeadlessService(
            nickname="t",
            ui_mode=True,
            listen_addrs=["/ip4/127.0.0.1/tcp/4001"],
        )
        addrs = service._resolve_listen_addrs()
        self.assertEqual([str(addr) for addr in addrs], ["/ip4/127.0.0.1/tcp/4001"])

    def test_unsupported_listen_protocol_rejected(self):
        service = HeadlessService(
            nickname="t", ui_mode=True, listen_addrs=["/ip4/127.0.0.1/sctp/4001"]
        )
        with self.assertRaisesRegex(ValueError, "expected a TCP or UDP multiaddr"):
            service._resolve_listen_addrs()

    def test_invalid_listen_addr_rejected(self):
        service = HeadlessService(
            nickname="t", ui_mode=True, listen_addrs=["not-a-multiaddr"]
        )
        with self.assertRaisesRegex(ValueError, "Invalid listen address"):
            service._resolve_listen_addrs()


class AddrsFactoryTests(unittest.TestCase):
    @staticmethod
    def _advertise(service, candidates):
        factory = service._make_addrs_factory()
        assert factory is not None
        return [
            str(addr)
            for addr in factory([multiaddr.Multiaddr(item) for item in candidates])
        ]

    def test_wildcard_rewritten_to_announce_host(self):
        service = HeadlessService(nickname="t", ui_mode=True, announce_host="10.0.0.5")
        result = self._advertise(service, ["/ip4/0.0.0.0/tcp/4001"])
        self.assertEqual(result, ["/ip4/10.0.0.5/tcp/4001"])

    def test_explicit_concrete_listener_is_not_rewritten(self):
        service = HeadlessService(nickname="t", ui_mode=True, announce_host="10.0.0.5")
        # Bound only to loopback: rewriting would advertise an interface the
        # peer is not listening on.
        result = self._advertise(service, ["/ip4/127.0.0.1/tcp/4001"])
        self.assertEqual(result, ["/ip4/127.0.0.1/tcp/4001"])

    def test_wildcard_dropped_for_other_family(self):
        service = HeadlessService(nickname="t", ui_mode=True, announce_host="10.0.0.5")
        self.assertEqual(self._advertise(service, ["/ip6/::/tcp/4001"]), [])

    def test_ipv6_announce_host_rewrites_ipv6_wildcard(self):
        service = HeadlessService(
            nickname="t", ui_mode=True, announce_host="2001:db8::1"
        )
        result = self._advertise(
            service, ["/ip6/::/tcp/4001", "/ip4/0.0.0.0/tcp/4001"]
        )
        self.assertEqual(result, ["/ip6/2001:db8::1/tcp/4001"])

    def test_duplicate_candidates_are_deduped(self):
        service = HeadlessService(nickname="t", ui_mode=True, announce_host="10.0.0.5")
        result = self._advertise(
            service,
            ["/ip4/0.0.0.0/tcp/4001", "/ip4/0.0.0.0/tcp/4001"],
        )
        self.assertEqual(result, ["/ip4/10.0.0.5/tcp/4001"])

    def test_wildcard_announce_host_rejected(self):
        service = HeadlessService(nickname="t", ui_mode=True, announce_host="0.0.0.0")
        with self.assertRaisesRegex(ValueError, "wildcard"):
            service._make_addrs_factory()

    def test_explicit_announce_disables_factory(self):
        service = HeadlessService(
            nickname="t",
            ui_mode=True,
            announce_addrs=["/ip4/10.0.0.5/tcp/4001"],
        )
        self.assertIsNone(service._make_addrs_factory())


class AnnounceValidationTests(unittest.TestCase):
    def test_wildcard_announce_addr_rejected(self):
        service = HeadlessService(
            nickname="t",
            ui_mode=True,
            announce_addrs=["/ip4/0.0.0.0/tcp/4001"],
        )
        with self.assertRaisesRegex(ValueError, "wildcard"):
            service._resolve_announce_addrs()

    def test_concrete_announce_addr_accepted(self):
        service = HeadlessService(
            nickname="t",
            ui_mode=True,
            announce_addrs=["/ip4/10.0.0.5/tcp/4001"],
        )
        addrs = service._resolve_announce_addrs()
        self.assertEqual([str(addr) for addr in addrs], ["/ip4/10.0.0.5/tcp/4001"])


class ClassifyTests(unittest.TestCase):
    def test_wildcard_detection(self):
        self.assertTrue(
            HeadlessService._is_wildcard_addr(multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/4001"))
        )
        self.assertTrue(
            HeadlessService._is_wildcard_addr(multiaddr.Multiaddr("/ip6/::/tcp/4001"))
        )
        self.assertFalse(
            HeadlessService._is_wildcard_addr(multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/4001"))
        )
        self.assertFalse(
            HeadlessService._is_wildcard_addr(multiaddr.Multiaddr("/ip6/::1/tcp/4001"))
        )

    def test_loopback_private_and_public(self):
        self.assertTrue(
            HeadlessService._classify_announced_addr(
                "/ip4/127.0.0.1/tcp/4001"
            ).startswith("loopback")
        )
        self.assertTrue(
            HeadlessService._classify_announced_addr(
                "/ip4/10.0.0.5/tcp/4001"
            ).startswith("private")
        )
        self.assertTrue(
            HeadlessService._classify_announced_addr(
                "/ip4/8.8.8.8/tcp/4001"
            ).startswith("public")
        )


class ListenerVerificationTests(unittest.TestCase):
    class _FakeHost:
        def __init__(self, addrs):
            self._addrs = addrs

        def get_transport_addrs(self):
            return [multiaddr.Multiaddr(item) for item in self._addrs]

    def test_ephemeral_port_request_matches_assigned_port(self):
        service = HeadlessService(nickname="t", ui_mode=True)
        service.host = self._FakeHost(["/ip4/0.0.0.0/tcp/43210"])
        # Requested port 0 means "whatever the OS assigns".
        service._verify_listeners([multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")])
        self.assertEqual(service.transport_addrs, ["/ip4/0.0.0.0/tcp/43210"])

    def test_wrong_host_fails_even_with_ephemeral_port(self):
        service = HeadlessService(nickname="t", ui_mode=True)
        service.host = self._FakeHost(["/ip4/127.0.0.1/tcp/43210"])
        with self.assertRaisesRegex(RuntimeError, "failed to start"):
            service._verify_listeners([multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")])

    def test_no_listener_raises(self):
        service = HeadlessService(nickname="t", ui_mode=True)
        service.host = self._FakeHost([])
        with self.assertRaisesRegex(RuntimeError, "did not start"):
            service._verify_listeners([multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/4001")])

    def test_requested_address_missing_raises(self):
        service = HeadlessService(nickname="t", ui_mode=True)
        service.host = self._FakeHost(["/ip4/0.0.0.0/tcp/4001"])
        with self.assertRaisesRegex(RuntimeError, "failed to start"):
            service._verify_listeners([multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/4002")])


class AddressIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._original_bootstrap = headless_module.BOOTSTRAP_PEERS
        headless_module.BOOTSTRAP_PEERS = []

    def tearDown(self):
        headless_module.BOOTSTRAP_PEERS = self._original_bootstrap

    def test_default_wildcard_listener_advertises_concrete_host(self):
        port = free_port()
        service = HeadlessService(
            nickname="t",
            port=port,
            seed=f"addr-{port}",
            ui_mode=True,
            listen_addrs=[f"/ip4/0.0.0.0/tcp/{port}"],
        )
        thread = start_service(service)
        try:
            self.assertTrue(service.ready, "service failed to start")
            self.assertEqual(
                service.transport_addrs, [f"/ip4/0.0.0.0/tcp/{port}"]
            )
            self.assertEqual(len(service.full_multiaddrs), 1)
            self.assertTrue(
                service.full_multiaddr.startswith(
                    f"/ip4/127.0.0.1/tcp/{port}/p2p/"
                )
            )
            self.assertNotIn("/ip4/0.0.0.0/", service.full_multiaddr)
            self.assertTrue(
                service.full_multiaddr.endswith(str(service.host.get_id()))
            )
        finally:
            service.request_stop()
            thread.join(10)

    def test_explicit_loopback_listener_is_advertised_as_bound(self):
        port = free_port()
        service = HeadlessService(
            nickname="t",
            seed=f"loop-{port}",
            ui_mode=True,
            listen_addrs=[f"/ip4/127.0.0.1/tcp/{port}"],
        )
        thread = start_service(service)
        try:
            self.assertTrue(service.ready, "service failed to start")
            self.assertEqual(
                service.transport_addrs, [f"/ip4/127.0.0.1/tcp/{port}"]
            )
            self.assertTrue(
                service.full_multiaddr.startswith(
                    f"/ip4/127.0.0.1/tcp/{port}/p2p/"
                )
            )
        finally:
            service.request_stop()
            thread.join(10)

    def test_explicit_announce_addr_is_used_verbatim(self):
        port = free_port()
        announce = f"/ip4/127.0.0.1/tcp/{port}"
        service = HeadlessService(
            nickname="t",
            seed=f"announce-{port}",
            ui_mode=True,
            port=port,
            listen_addrs=[announce],
            announce_addrs=[announce],
        )
        thread = start_service(service)
        try:
            self.assertTrue(service.ready, "service failed to start")
            self.assertEqual(
                service.full_multiaddrs,
                [f"{announce}/p2p/{service.host.get_id()}"],
            )
        finally:
            service.request_stop()
            thread.join(10)

    def test_two_peers_connect_and_publish(self):
        port_a, port_b = free_port(), free_port()
        service_a = HeadlessService(
            nickname="A",
            port=port_a,
            seed=f"two-a-{port_a}",
            ui_mode=True,
            listen_addrs=[f"/ip4/127.0.0.1/tcp/{port_a}"],
        )
        service_b = HeadlessService(
            nickname="B",
            port=port_b,
            seed=f"two-b-{port_b}",
            ui_mode=True,
            listen_addrs=[f"/ip4/127.0.0.1/tcp/{port_b}"],
        )
        thread_a = start_service(service_a)
        thread_b = start_service(service_b)
        try:
            self.assertTrue(service_a.ready, "peer A failed to start")
            self.assertTrue(service_b.ready, "peer B failed to start")

            self.assertTrue(service_a.connect_to_peer(service_b.full_multiaddr))
            deadline = time.monotonic() + 10
            while (
                str(service_b.host.get_id())
                not in {str(peer) for peer in service_a.host.get_connected_peers()}
                and time.monotonic() < deadline
            ):
                time.sleep(0.1)
            self.assertIn(
                str(service_b.host.get_id()),
                {str(peer) for peer in service_a.host.get_connected_peers()},
            )

            self.assertTrue(service_a.send_message("test-connectivity"))
            deadline = time.monotonic() + 10
            messages = []
            while time.monotonic() < deadline:
                messages = service_b.get_topic_messages("universal-connectivity")
                if any(m.get("message") == "test-connectivity" for m in messages):
                    break
                time.sleep(0.1)
            self.assertIn(
                "test-connectivity",
                [m.get("message") for m in messages],
            )
        finally:
            service_a.request_stop()
            service_b.request_stop()
            thread_a.join(10)
            thread_b.join(10)


if __name__ == "__main__":
    unittest.main()
