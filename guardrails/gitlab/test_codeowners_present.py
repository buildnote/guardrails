#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class CodeownersPresentTest(GuardrailTestCase):
    SCRIPT = "codeowners-present.py"
    COLLECT = ["gitlab"]

    def test_passes_a_project_that_names_owners(self):
        directory = self.workspace(CODEOWNERS="[Backend][2] @company/backend\n/api/\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_project_with_no_codeowners(self):
        self.assert_violation(self.check(self.workspace()), "The project declares no code owners")

    def test_fails_a_codeowners_that_declares_no_rules(self):
        directory = self.workspace(CODEOWNERS="# owners live in the handbook\n")

        violation = self.assert_violation(self.check(directory), "declares no rule in any section")

        self.assertEqual(violation["evidence"], "CODEOWNERS")

    def test_fails_a_section_header_with_no_rules_under_it(self):
        directory = self.workspace(CODEOWNERS="[Backend] @company/backend\n")

        self.assert_violation(self.check(directory), "declares no rule in any section")

    def test_reads_the_gitlab_location(self):
        directory = self.workspace(**{".gitlab/CODEOWNERS": "*  @company/platform\n"})

        self.assert_passed(self.check(directory))


if __name__ == "__main__":
    unittest.main()
