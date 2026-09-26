#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class TeamOwnedTest(GuardrailTestCase):
    SCRIPT = "codeowners-team-owned.py"
    COLLECT = ["github"]

    def test_passes_a_rule_owned_by_a_team(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_rule_owned_only_by_individuals(self):
        directory = self.workspace(CODEOWNERS="*  @dana @sam\n")

        violation = self.assert_violation(self.check(directory), "is owned only by individuals (@dana, @sam)")

        self.assertEqual(violation["evidence"], "CODEOWNERS:1 *")

    def test_fails_an_email_owner(self):
        directory = self.workspace(CODEOWNERS="*  dana@company.com\n")

        self.assert_violation(self.check(directory), "is owned only by individuals")

    def test_accepts_individuals_beside_a_team_by_default(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform @dana\n")

        self.assert_passed(self.check(directory))

    def test_reports_individuals_beside_a_team_when_told_to(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform @dana\n")

        self.assert_violation(
            self.check(directory, allowIndividuals="false"), "names individuals beside its team (@dana)"
        )

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".github/workflows/build.yml": "name: b\non: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
