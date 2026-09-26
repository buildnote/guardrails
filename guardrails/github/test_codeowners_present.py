#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class CodeownersPresentTest(GuardrailTestCase):
    SCRIPT = "codeowners-present.py"
    COLLECT = ["github"]

    def test_passes_a_repository_that_names_owners(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_repository_with_no_codeowners(self):
        self.assert_violation(self.check(self.workspace()), "The repository declares no code owners")

    def test_fails_a_codeowners_that_declares_no_rules(self):
        directory = self.workspace(CODEOWNERS="# owners live in the wiki\n")

        violation = self.assert_violation(self.check(directory), "declares no rules")

        self.assertEqual(violation["evidence"], "CODEOWNERS")

    def test_reads_the_github_location(self):
        directory = self.workspace(**{".github/CODEOWNERS": "*  @company/platform\n"})

        self.assert_passed(self.check(directory))


if __name__ == "__main__":
    unittest.main()
