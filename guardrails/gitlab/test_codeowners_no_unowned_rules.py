#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class NoUnownedRulesTest(GuardrailTestCase):
    SCRIPT = "codeowners-no-unowned-rules.py"
    COLLECT = ["gitlab"]

    def test_passes_a_file_where_every_rule_names_an_owner(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n/api/ @company/backend\n")

        self.assert_passed(self.check(directory))

    def test_passes_a_rule_that_inherits_its_sections_default_owners(self):
        directory = self.workspace(CODEOWNERS="[Generated] @company/platform\n/service/generated/\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_rule_no_owner_and_no_section_default_covers(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n\n[Generated]\n/service/generated/\n")

        violation = self.assert_violation(
            self.check(directory), "the [Generated] section it sits in declares no default owners"
        )

        self.assertEqual(violation["evidence"], "CODEOWNERS:4 /service/generated/")

    def test_names_the_default_section_a_rule_above_the_first_header_sits_in(self):
        directory = self.workspace(CODEOWNERS="/vendor/\n\n[Backend] @company/backend\n/api/\n")

        self.assert_violation(self.check(directory), "the [codeowners] section it sits in")

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".gitlab-ci.yml": "build:\n  script:\n    - make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
