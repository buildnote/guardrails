#!/usr/bin/env python3
import os, sys
LIB = os.environ.get("GUARDRAIL_LIB_DIR") or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LIB)

import re
import unittest

from guardrail_testing import fixtures
from guardrail_toml import parse, unsupported

fixture = fixtures(__file__)

REASON = re.compile(r"^[a-z][a-z ]+ at line [0-9]+$")

CARGO = fixture("cargo.toml")

PYPROJECT = fixture("pyproject.toml")


class ParseTest(unittest.TestCase):
    def test_reads_a_table_of_strings(self):
        document = parse(CARGO)

        self.assertEqual(document["package"]["name"], "widget")
        self.assertEqual(document["package"]["edition"], "2021")
        self.assertEqual(document["package"]["rust-version"], "1.76")

    def test_reads_an_inline_table(self):
        document = parse(CARGO)

        self.assertEqual(document["dependencies"]["serde"]["version"], "1.0.197")
        self.assertEqual(document["dependencies"]["serde"]["features"], ["derive"])

    def test_reads_a_bare_string_value(self):
        self.assertEqual(parse(CARGO)["dependencies"]["anyhow"], "1.0.81")

    def test_reads_an_array_of_strings(self):
        self.assertEqual(parse(CARGO)["workspace"]["members"], ["crates/core", "crates/cli"])

    def test_reads_a_multiline_array(self):
        self.assertEqual(parse(PYPROJECT)["project"]["dependencies"], ["httpx>=0.27", "pydantic~=2.6"])

    def test_reads_a_dotted_header(self):
        self.assertEqual(parse(PYPROJECT)["project"]["optional-dependencies"]["dev"], ["pytest>=8.0"])
        self.assertEqual(parse(PYPROJECT)["tool"]["ruff"]["line-length"], 120)

    def test_reads_a_dotted_key(self):
        self.assertEqual(parse("a.b.c = 1\n"), {"a": {"b": {"c": 1}}})

    def test_reads_booleans_integers_and_floats(self):
        document = parse("yes = true\nno = false\ncount = 1_000\nratio = 1.5\n")

        self.assertEqual(document, {"yes": True, "no": False, "count": 1000, "ratio": 1.5})

    def test_reads_a_literal_string(self):
        self.assertEqual(parse("path = 'C:\\\\widget'\n"), {"path": "C:\\\\widget"})

    def test_reads_an_escape_in_a_basic_string(self):
        self.assertEqual(parse('text = "a\\tb\\u0041"\n'), {"text": "a\tbA"})

    def test_reads_a_multiline_basic_string(self):
        self.assertEqual(parse('text = """\nline\n"""\n'), {"text": "line\n"})

    def test_reads_an_array_of_tables(self):
        document = parse("[[bin]]\nname = \"a\"\n\n[[bin]]\nname = \"b\"\n")

        self.assertEqual([it["name"] for it in document["bin"]], ["a", "b"])

    def test_reads_a_quoted_key(self):
        self.assertEqual(parse('["a.b"]\nc = 1\n'), {"a.b": {"c": 1}})

    def test_ignores_comments_and_blank_lines(self):
        self.assertEqual(parse("# leading\n\nname = \"widget\"  # trailing\n"), {"name": "widget"})

    def test_reads_a_date_as_the_text_it_is_written_as(self):
        self.assertEqual(parse("released = 2026-08-26\n"), {"released": "2026-08-26"})

    def test_reads_an_empty_document(self):
        self.assertEqual(parse(""), {})


class UnsupportedTest(unittest.TestCase):
    def rejected(self, text, reason):
        found = unsupported(text)

        self.assertEqual(found, reason)
        self.assertRegex(found, REASON)
        self.assertIsNone(parse(text))

    def test_rejects_a_redefined_key(self):
        self.rejected("a = 1\na = 2\n", "redefined key at line 2")

    def test_rejects_an_unterminated_string(self):
        self.rejected("a = \"open\n", "unterminated string at line 1")

    def test_rejects_an_unterminated_header(self):
        self.rejected("[package\nname = \"a\"\n", "unterminated header at line 1")

    def test_rejects_a_missing_equals(self):
        self.rejected("name \"widget\"\n", "expected an equals at line 1")

    def test_rejects_an_unterminated_array(self):
        self.rejected("a = [1, 2\n", "unterminated array at line 2")

    def test_rejects_content_after_a_value(self):
        self.rejected("a = 1 b\n", "unknown value at line 1")

    def test_accepts_what_it_can_read(self):
        self.assertIsNone(unsupported(CARGO))
        self.assertIsNone(unsupported(PYPROJECT))


if __name__ == "__main__":
    unittest.main()
