"""API trust-boundary defaults and headless import independence."""

import inspect
import os
import subprocess
import sys
import unittest

from api.server import DEFAULT_API_HOST, TornadoServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_BLOCK_TEXTUAL = """
import importlib.abc
import sys


class _BlockTextual(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "textual":
            raise ImportError(fullname + " is blocked for this test")
        return None


sys.meta_path.insert(0, _BlockTextual())
"""


def _run_python(code: str, timeout: int = 90):
    env = dict(os.environ, PYTHONPATH=ROOT)
    env.pop("UC_DATA_DIR", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class ApiTrustBoundaryTests(unittest.TestCase):
    def test_api_binds_loopback_by_default(self):
        self.assertEqual(DEFAULT_API_HOST, "127.0.0.1")
        signature = inspect.signature(TornadoServer.__init__)
        self.assertEqual(signature.parameters["host"].default, DEFAULT_API_HOST)

    def test_help_exposes_api_host(self):
        result = _run_python(
            "import runpy, sys\n"
            "sys.argv = ['main.py', '--help']\n"
            "runpy.run_path('main.py', run_name='__main__')\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--api-host", result.stdout)
        self.assertIn("127.0.0.1", result.stdout)


class HeadlessImportTests(unittest.TestCase):
    def test_headless_modules_import_without_textual(self):
        code = _BLOCK_TEXTUAL + """
import main
import core.headless as headless
import app.chatroom as chatroom
import api.server as tornado_server
import api.base
import app.runtime
import app.paths

leaked = sorted({name.split(".")[0] for name in sys.modules} & {"textual"})
if leaked:
    raise SystemExit(f"headless import pulled in a UI framework: {leaked}")
print("HEADLESS_OK")
"""
        result = _run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HEADLESS_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
