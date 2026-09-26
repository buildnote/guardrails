#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class OwnersPerRuleTest(GuardrailTestCase):
    SCRIPT = "codeowners-owners-per-rule.py"
    COLLECT = ["github"]

    def test_passes_a_rule_within_the_bounds(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform @dana\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_rule_below_the_floor(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n")

        self.assert_violation(self.check(directory, minOwners=2), "is owned by 1, fewer than the 2 expected")

    def test_fails_a_rule_above_the_ceiling(self):
        owners = " ".join("@company/team%d" % it for it in range(1, 8))
        directory = self.workspace(CODEOWNERS="*  %s\n" % owners)

        violation = self.assert_violation(self.check(directory), "is owned by 7, more than the 5 a rule may name")

        self.assertEqual(violation["evidence"], "CODEOWNERS:1 * (7 owners)")

    def test_leaves_a_rule_with_no_owners_to_the_guardrail_for_it(self):
        directory = self.workspace(CODEOWNERS="/vendor/\n")

        self.assert_passed(self.check(directory))

    def test_takes_no_ceiling_at_all(self):
        owners = " ".join("@company/team%d" % it for it in range(1, 8))
        directory = self.workspace(CODEOWNERS="*  %s\n" % owners)

        self.assert_passed(self.check(directory, maxOwners=0))

    def test_skips_when_the_bound_is_not_a_number(self):
        directory = self.workspace(CODEOWNERS="*  @company/platform\n")

        self.assert_skipped(self.check(directory, maxOwners="five"), "maxOwners 'five' is not a number")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".github/workflows/build.yml": "name: b\non: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
