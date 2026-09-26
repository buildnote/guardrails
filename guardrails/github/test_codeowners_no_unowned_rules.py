#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class NoUnownedRulesTest(GuardrailTestCase):
    SCRIPT = "codeowners-no-unowned-rules.py"
    COLLECT = ["github"]

    def test_passes_rules_that_all_name_owners(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n/docs/  @company/docs\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_rule_that_names_none(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n/vendor/\n")

        violation = self.assert_violation(self.check(directory), "names no owner for /vendor/")

        self.assertEqual(violation["evidence"], "CODEOWNERS:2 /vendor/")

    def test_fails_a_bracketed_line_because_github_reads_it_as_a_pattern(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n[Docs]\n")

        violation = self.assert_violation(self.check(directory), "names no owner for [Docs]")

        self.assertEqual(violation["evidence"], "CODEOWNERS:2 [Docs]")

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".github/workflows/build.yml": "name: b\non: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
