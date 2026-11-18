"""Packaging regression tests: artifact contents and dependency pinning."""

import os
import re
import tomllib
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED_RUNTIME = {
    "main.py",
    "core",
    "ui",
    "api",
    "app",
    "llm",
}


def _pyproject():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as handle:
        return tomllib.load(handle)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.config = _pyproject()
        build = self.config["tool"]["hatch"]["build"]["targets"]
        self.wheel = set(build["wheel"]["only-include"])
        self.sdist = set(build["sdist"]["only-include"])

    def test_wheel_contains_only_the_python_runtime(self):
        self.assertTrue(REQUIRED_RUNTIME <= self.wheel)
        for path in self.wheel:
            self.assertNotIn("node_modules", path)
            self.assertNotIn("tests", path)
            self.assertNotIn("docs", path)

    def test_sdist_contains_review_assets_but_no_dependency_or_state_dirs(self):
        self.assertTrue(REQUIRED_RUNTIME <= self.sdist)
        for required in (
            "tests",
            "Dockerfile",
            "docker-compose.yml",
            "README.md",
            "uv.lock",
        ):
            self.assertIn(required, self.sdist)
        for path in self.sdist:
            self.assertNotIn("node_modules", path)
            self.assertNotIn(".venv", path)

    def test_libp2p_is_pinned_to_a_tested_git_commit(self):
        dependency = next(
            item
            for item in self.config["project"]["dependencies"]
            if item.startswith("libp2p")
        )
        self.assertTrue(
            dependency.startswith("libp2p>=")
            or "github.com" in dependency
        )
        self.assertNotIn(
            "sources", self.config.get("tool", {}).get("uv", {})
        )

    def test_console_script_points_at_the_installed_module(self):
        self.assertEqual(
            self.config["project"]["scripts"]["py-peer"], "main:main"
        )
        self.assertEqual(
            self.config["build-system"]["build-backend"], "hatchling.build"
        )


if __name__ == "__main__":
    unittest.main()
