"""CLI argument parsing and validation tests."""

import argparse
import unittest

from app.cli import build_parser, parse_args
from core.constants import DEFAULT_PORT, MAX_BASE_PORT
from main import _port_type


class PortTypeTests(unittest.TestCase):
    def test_accepts_zero_and_the_upper_bound(self):
        self.assertEqual(_port_type("0"), 0)
        self.assertEqual(_port_type("4001"), 4001)
        self.assertEqual(_port_type(str(MAX_BASE_PORT)), MAX_BASE_PORT)

    def test_rejects_values_without_room_for_derived_ports(self):
        for value in (str(MAX_BASE_PORT + 1), "65535", "70000", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    _port_type(value)

    def test_rejects_non_integers(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _port_type("http")


class CliParserTests(unittest.TestCase):
    def test_default_arguments(self):
        args = parse_args([])
        self.assertEqual(args.port, DEFAULT_PORT)
        self.assertFalse(args.headless)
        self.assertFalse(args.ui)
        self.assertFalse(args.api)
        self.assertEqual(args.announce_host, "127.0.0.1")
        self.assertEqual(args.api_port, 8765)
        self.assertEqual(args.max_connections, 500)

    def test_explicit_arguments(self):
        args = parse_args([
            "--nick", "tester",
            "--headless",
            "-p", "4005",
            "-c", "/ip4/127.0.0.1/tcp/4001",
            "--api",
        ])
        self.assertEqual(args.nick, "tester")
        self.assertTrue(args.headless)
        self.assertEqual(args.port, 4005)
        self.assertEqual(args.connect, ["/ip4/127.0.0.1/tcp/4001"])
        self.assertTrue(args.api)


if __name__ == "__main__":
    unittest.main()
