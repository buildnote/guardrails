#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class OwnersPerRuleTest(GuardrailTestCase):
    SCRIPT = "codeowners-owners-per-rule.py"
    COLLECT = ["gitlab"]

    def test_passes_a_rule_naming_one_owner(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_rule_naming_more_owners_than_the_ceiling(self):
        directory = self.workspace(CODEOWNERS="* @a/one @a/two @a/three\n")

        violation = self.assert_violation(
            self.check(directory, maxOwners="2"), "* is owned by 3, more than the 2 a rule may name"
        )

        self.assertEqual(violation["evidence"], "CODEOWNERS:1 * (3 owners)")

    def test_counts_the_owners_a_rule_inherits_from_its_section(self):
        directory = self.workspace(CODEOWNERS="[Backend] @a/one @a/two @a/three\n/api/\n")

        self.assert_violation(
            self.check(directory, maxOwners="2"),
            "/api/ is owned by 3 inherited from [Backend], more than the 2 a rule may name",
        )

    def test_fails_a_rule_naming_fewer_owners_than_the_floor(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n")

        self.assert_violation(self.check(directory, minOwners="2"), "fewer than the 2 expected")

    def test_ignores_a_rule_with_no_owners_at_all(self):
        directory = self.workspace(CODEOWNERS="[Generated]\n/service/generated/\n")

        self.assert_passed(self.check(directory))

    def test_takes_a_maximum_of_zero_as_no_ceiling(self):
        directory = self.workspace(CODEOWNERS="* @a/one @a/two @a/three @a/four @a/five @a/six\n")

        self.assert_passed(self.check(directory, maxOwners="0"))

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".gitlab-ci.yml": "build:\n  script:\n    - make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
