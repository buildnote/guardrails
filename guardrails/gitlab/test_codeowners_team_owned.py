#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class TeamOwnedTest(GuardrailTestCase):
    SCRIPT = "codeowners-team-owned.py"
    COLLECT = ["gitlab"]

    def test_passes_a_rule_owned_by_a_group(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n")

        self.assert_passed(self.check(directory))

    def test_passes_a_rule_owned_by_a_subgroup(self):
        directory = self.workspace(CODEOWNERS="* @company/security/appsec\n")

        self.assert_passed(self.check(directory))

    def test_passes_a_rule_that_inherits_a_group_from_its_section(self):
        directory = self.workspace(CODEOWNERS="[Backend] @company/backend\n/api/\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_rule_owned_only_by_individuals(self):
        directory = self.workspace(CODEOWNERS="* @dana @sam\n")

        violation = self.assert_violation(self.check(directory), "is owned only by individuals (@dana, @sam)")

        self.assertEqual(violation["evidence"], "CODEOWNERS:1 *")

    def test_fails_an_email_owner(self):
        directory = self.workspace(CODEOWNERS="* dana@company.com\n")

        self.assert_violation(self.check(directory), "is owned only by individuals")

    def test_names_the_section_a_rule_inherits_its_individuals_from(self):
        directory = self.workspace(CODEOWNERS="[Backend] @dana\n/api/\n")

        self.assert_violation(self.check(directory), "(@dana) inherited from [Backend]")

    def test_accepts_individuals_beside_a_group_by_default(self):
        directory = self.workspace(CODEOWNERS="* @company/platform @dana\n")

        self.assert_passed(self.check(directory))

    def test_reports_individuals_beside_a_group_when_told_to(self):
        directory = self.workspace(CODEOWNERS="* @company/platform @dana\n")

        self.assert_violation(
            self.check(directory, allowIndividuals="false"), "names individuals beside its group (@dana)"
        )

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".gitlab-ci.yml": "build:\n  script:\n    - make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
