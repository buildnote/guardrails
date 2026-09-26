#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

WRITTEN = "# Contributing\n\n1. Build with gradle.\n2. Tests pass.\n3. One reviewer approves.\n4. Rebase, never merge.\n"


class ContributingTest(GuardrailTestCase):
    SCRIPT = "contributing.py"
    COLLECT = ["files"]

    def test_passes_a_guide_that_says_something(self):
        self.assert_passed(self.check(self.workspace(**{"CONTRIBUTING.md": WRITTEN})))

    def test_fails_a_missing_guide(self):
        violation = self.assert_violation(self.check(self.workspace()), "No contribution guide at CONTRIBUTING.md")

        self.assertEqual(violation["evidence"], "CONTRIBUTING.md")

    def test_fails_a_guide_shorter_than_the_floor(self):
        directory = self.workspace(**{"CONTRIBUTING.md": "# Contributing\n\nAsk somebody.\n"})

        self.assert_violation(self.check(directory), "has 2 non-blank lines, fewer than the 5 expected")

    def test_honours_the_path_it_is_given(self):
        directory = self.workspace(**{".github/CONTRIBUTING.md": WRITTEN})

        self.assert_passed(self.check(directory, path=".github/CONTRIBUTING.md"))
        self.assert_violation(self.check(directory), "No contribution guide at CONTRIBUTING.md")

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{"CONTRIBUTING.md": WRITTEN})

        self.assert_skipped(self.check(directory, minLines="five"), "minLines 'five' is not a number")


if __name__ == "__main__":
    unittest.main()
