"""Regression tests for the shared JSON string-field validator."""

import unittest

from api.base import parse_string_field


class ParseStringFieldTests(unittest.TestCase):
    def test_strips_whitespace(self):
        self.assertEqual(parse_string_field({"message": "  hi  "}, "message"), "hi")

    def test_required_missing_field(self):
        with self.assertRaisesRegex(ValueError, "field is required"):
            parse_string_field({}, "message", required=True)

    def test_required_blank_field(self):
        with self.assertRaisesRegex(ValueError, "field is required"):
            parse_string_field({"message": "   "}, "message", required=True)

    def test_non_string_is_a_client_error(self):
        # This used to become AttributeError -> HTTP 500 in every handler that
        # called body.get(...).strip().
        with self.assertRaisesRegex(ValueError, "must be a string"):
            parse_string_field({"message": 123}, "message")

    def test_optional_default(self):
        self.assertEqual(
            parse_string_field({}, "file_name", default="unknown"), "unknown"
        )

    def test_max_length(self):
        with self.assertRaisesRegex(ValueError, "at most 3"):
            parse_string_field({"topic": "abcd"}, "topic", max_length=3)


if __name__ == "__main__":
    unittest.main()
