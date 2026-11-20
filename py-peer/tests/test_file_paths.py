"""Regression tests for the /files/share path containment policy."""

import os
import tempfile
import unittest

from api.files import _is_within


class PathContainmentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.inside = os.path.join(self.root, "inside.txt")
        with open(self.inside, "w", encoding="utf-8") as f:
            f.write("inside")
        self._outside_tmp = tempfile.TemporaryDirectory()
        self.outside = os.path.join(self._outside_tmp.name, "secret.txt")
        with open(self.outside, "w", encoding="utf-8") as f:
            f.write("secret")

    def tearDown(self):
        self._tmp.cleanup()
        self._outside_tmp.cleanup()

    def test_file_inside_directory(self):
        self.assertTrue(_is_within(self.inside, self.root))

    def test_file_outside_directory(self):
        self.assertFalse(_is_within(self.outside, self.root))

    def test_parent_reference_cannot_escape(self):
        escape = os.path.join(self.root, "..", os.path.basename(self.outside))
        self.assertFalse(_is_within(escape, self.root))

    def test_symlink_escape_is_rejected(self):
        link = os.path.join(self.root, "link.txt")
        try:
            os.symlink(self.outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available on this platform")
        # realpath resolves the link target, so the containment check rejects it.
        self.assertFalse(_is_within(link, self.root))

    def test_symlink_inside_directory_is_allowed(self):
        link = os.path.join(self.root, "inside-link.txt")
        try:
            os.symlink(self.inside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available on this platform")
        self.assertTrue(_is_within(link, self.root))


if __name__ == "__main__":
    unittest.main()
