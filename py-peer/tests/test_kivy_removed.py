"""Kivy was retired in Phase 5; the core runtime must not reference it."""

import glob
import os
import re
import subprocess
import sys
import tomllib
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(ROOT, "pyproject.toml")

# Make kivy/kivymd unimportable even if an old environment still has them.
_BLOCK_KIVY = """
import importlib.abc
import sys


class _BlockKivy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"kivy", "kivymd"}:
            raise ImportError(fullname + " is not installed (blocked for test)")
        return None


sys.meta_path.insert(0, _BlockKivy())
"""


def _run_python(code: str, *args: str, timeout: int = 90):
    env = dict(os.environ, PYTHONPATH=ROOT)
    env.pop("UC_DATA_DIR", None)
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _dependency_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[; ]", requirement.strip(), maxsplit=1)[0].lower()


class KivyRemovalTests(unittest.TestCase):
    def test_kivy_ui_module_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "kivy_ui.py")))
        self.assertFalse(
            os.path.exists(os.path.join(ROOT, "assets", "images", "py-peer-kivy.png"))
        )

    def test_pyproject_has_no_kivy_dependency_or_extra(self):
        with open(PYPROJECT, "rb") as handle:
            project = tomllib.load(handle)["project"]

        required = {_dependency_name(dep) for dep in project["dependencies"]}
        self.assertNotIn("kivy", required)
        self.assertNotIn("kivymd", required)

        extras = project.get("optional-dependencies", {})
        self.assertNotIn("kivy", extras)
        declared = {
            _dependency_name(dep)
            for group in extras.values()
            for dep in group
        }
        self.assertFalse({"kivy", "kivymd"} & declared)

    def test_help_has_no_kivy_flag_and_argparse_rejects_it(self):
        help_result = _run_python(
            "import runpy, sys\nsys.argv = ['main.py', '--help']\n"
            "runpy.run_path('main.py', run_name='__main__')\n"
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertNotIn("--kivy", help_result.stdout)

        rejected = _run_python(
            "import runpy, sys\nsys.argv = ['main.py', '--kivy', '--nick', 'x']\n"
            "runpy.run_path('main.py', run_name='__main__')\n"
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("unrecognized arguments: --kivy", rejected.stderr)

    def test_core_modules_still_import_with_kivy_blocked(self):
        code = _BLOCK_KIVY + """
import main
import core.headless as headless
import app.chatroom as chatroom
import api.server as tornado_server
import ui
import api.base
import app.runtime
import app.paths

leaked = sorted(
    {name.split(".")[0] for name in sys.modules} & {"kivy", "kivymd"}
)
if leaked:
    raise SystemExit(f"core import pulled in removed UI packages: {leaked}")
print("CORE_OK")
"""
        result = _run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CORE_OK", result.stdout)

    def test_no_application_module_references_kivy(self):
        offenders = []
        for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
            relative = os.path.relpath(path, ROOT)
            if relative.startswith((".venv", "tests", "llm")):
                continue
            if "__pycache__" in relative:
                continue
            with open(path, encoding="utf-8", errors="ignore") as handle:
                for number, line in enumerate(handle, 1):
                    if re.search(r"\bkivy", line, re.IGNORECASE):
                        offenders.append(f"{relative}:{number}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
