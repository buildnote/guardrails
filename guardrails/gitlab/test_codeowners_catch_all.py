#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class CatchAllRuleTest(GuardrailTestCase):
    SCRIPT = "codeowners-catch-all.py"
    COLLECT = ["gitlab"]

    def test_passes_a_catch_all_in_a_required_section(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n\n[Backend][2] @company/backend\n/api/\n")

        self.assert_passed(self.check(directory))

    def test_passes_a_catch_all_that_inherits_its_sections_default_owners(self):
        directory = self.workspace(CODEOWNERS="[Platform] @company/platform\n*\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_file_of_narrow_sections_only(self):
        directory = self.workspace(CODEOWNERS="[Backend] @company/backend\n/api/\n\n[Docs] @company/docs\n/docs/\n")

        violation = self.assert_violation(self.check(directory), "declares an owned catch-all rule")

        self.assertEqual(violation["evidence"], "CODEOWNERS")

    def test_fails_a_catch_all_that_names_no_owner(self):
        directory = self.workspace(CODEOWNERS="[Backend] @company/backend\n/api/\n\n[Everything]\n*\n")

        self.assert_violation(self.check(directory), "declares an owned catch-all rule")

    def test_fails_when_the_only_catch_all_sits_in_an_optional_section(self):
        directory = self.workspace(CODEOWNERS="^[Advisory] @company/platform\n*\n")

        self.assert_violation(
            self.check(directory), "sit in optional sections ([Advisory]), whose approval GitLab never requires"
        )

    def test_honours_the_patterns_it_is_given(self):
        directory = self.workspace(CODEOWNERS="[Platform] @company/platform\n/\n")

        self.assert_violation(self.check(directory), "declares an owned catch-all rule")
        self.assert_passed(self.check(directory, patterns="/"))

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".gitlab-ci.yml": "build:\n  script:\n    - make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
