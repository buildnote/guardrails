#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class CatchAllRuleTest(GuardrailTestCase):
    SCRIPT = "codeowners-catch-all.py"
    COLLECT = ["github"]

    def test_passes_a_file_with_a_catch_all(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n/docs/  @company/docs\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_file_of_narrow_rules_only(self):
        directory = self.workspace(CODEOWNERS="/api/  @company/backend\n/docs/  @company/docs\n")

        violation = self.assert_violation(self.check(directory), "declares no owned catch-all rule")

        self.assertEqual(violation["evidence"], "CODEOWNERS")

    def test_fails_a_catch_all_that_names_no_owner(self):
        directory = self.workspace(CODEOWNERS="/api/  @company/backend\n*\n")

        self.assert_violation(self.check(directory), "declares no owned catch-all rule")

    def test_honours_the_patterns_it_is_given(self):
        directory = self.workspace(CODEOWNERS="/  @company/platform\n")

        self.assert_violation(self.check(directory), "declares no owned catch-all rule")
        self.assert_passed(self.check(directory, patterns="/"))

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".github/workflows/build.yml": "name: b\non: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
