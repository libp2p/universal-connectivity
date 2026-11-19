"""CLI argument validation for the base listen port."""

import argparse
import unittest

from core.constants import MAX_BASE_PORT
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


if __name__ == "__main__":
    unittest.main()
