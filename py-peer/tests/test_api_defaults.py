"""Default trust boundary for the local HTTP API."""

import inspect
import unittest

from api.server import DEFAULT_API_HOST, TornadoServer


class ApiDefaultTests(unittest.TestCase):
    def test_api_binds_loopback_by_default(self):
        self.assertEqual(DEFAULT_API_HOST, "127.0.0.1")
        signature = inspect.signature(TornadoServer.__init__)
        self.assertEqual(signature.parameters["host"].default, DEFAULT_API_HOST)


if __name__ == "__main__":
    unittest.main()
