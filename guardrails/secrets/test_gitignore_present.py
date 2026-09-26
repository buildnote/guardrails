#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

IGNORED = "build/\n.gradle/\n.env\n*.pem\n"


class GitignorePresentTest(GuardrailTestCase):
    SCRIPT = "gitignore-present.py"
    COLLECT = ["files"]

    def test_passes_a_repository_that_ignores_its_output(self):
        self.assert_passed(self.check(self.workspace(**{".gitignore": IGNORED})))

    def test_fails_a_repository_with_no_ignore_file(self):
        violation = self.assert_violation(self.check(self.workspace()), "No .gitignore")

        self.assertEqual(violation["evidence"], ".gitignore")

    def test_fails_an_ignore_file_that_ignores_nothing(self):
        directory = self.workspace(**{".gitignore": "\n\n"})

        self.assert_violation(self.check(directory), "ignores 0 paths, fewer than the 1 expected")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{".gitignore": IGNORED})

        self.assert_passed(self.check(directory, minLines=4))
        self.assert_violation(self.check(directory, minLines=5), "fewer than the 5 expected")

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{".gitignore": IGNORED})

        self.assert_skipped(self.check(directory, minLines="one"), "minLines 'one' is not a number")


if __name__ == "__main__":
    unittest.main()
