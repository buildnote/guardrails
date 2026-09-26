#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class CodeownersParsesTest(GuardrailTestCase):
    SCRIPT = "codeowners-parses.py"
    COLLECT = ["github"]

    def test_passes_a_file_of_rules(self):
        directory = self.workspace(CODEOWNERS="# owners\n\n*  @company/platform\n/docs/  @company/docs\n")

        self.assert_passed(self.check(directory))

    def test_fails_an_owner_that_is_no_owner(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n/docs/  platform-team\n")

        violation = self.assert_violation(self.check(directory), "carries a line that is no rule")

        self.assertIn(
            "'platform-team' is not a GitHub user, a GitHub team or an email address", violation["message"]
        )
        self.assertEqual(violation["evidence"], "CODEOWNERS: 2")

    def test_passes_a_bracketed_line_because_github_has_no_section_headers(self):
        directory = self.workspace(CODEOWNERS="[Docs]\n*  @company/platform\n")

        self.assert_passed(self.check(directory))

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".github/workflows/build.yml": "name: b\non: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
