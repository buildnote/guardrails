#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

WRITTEN = "\n".join("Line %d of a README that says something." % line for line in range(1, 13))


class ReadmeTest(GuardrailTestCase):
    SCRIPT = "readme.py"
    COLLECT = ["files"]

    def test_passes_a_readme_that_says_something(self):
        self.assert_passed(self.check(self.workspace(**{"README.md": WRITTEN})))

    def test_fails_a_missing_readme(self):
        violation = self.assert_violation(self.check(self.workspace()), "No README at README.md")

        self.assertEqual(violation["evidence"], "README.md")

    def test_fails_a_readme_shorter_than_the_floor(self):
        directory = self.workspace(**{"README.md": "# Project\n\nA stub.\n"})

        violation = self.assert_violation(
            self.check(directory),
            "README at README.md has 2 non-blank lines, fewer than the 10 expected",
        )

        self.assertEqual(violation["evidence"], "README.md (2 non-blank lines)")

    def test_counts_only_non_blank_lines(self):
        directory = self.workspace(**{"README.md": "# Project\n" + "\n" * 40 + "Written by nobody.\n"})

        self.assert_violation(self.check(directory), "has 2 non-blank lines")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"README.md": "# Project\n\nA stub.\n"})

        self.assert_passed(self.check(directory, minLines=2))
        self.assert_violation(self.check(directory, minLines=3), "fewer than the 3 expected")

    def test_honours_the_path_it_is_given(self):
        directory = self.workspace(**{"docs/index.md": WRITTEN})

        self.assert_passed(self.check(directory, path="docs/index.md"))
        self.assert_violation(self.check(directory, path="docs/missing.md"), "No README at docs/missing.md")

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{"README.md": WRITTEN})

        self.assert_skipped(self.check(directory, minLines="ten"), "minLines 'ten' is not a number")


if __name__ == "__main__":
    unittest.main()
