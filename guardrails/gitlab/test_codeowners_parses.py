#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)


class CodeownersParsesTest(GuardrailTestCase):
    SCRIPT = "codeowners-parses.py"
    COLLECT = ["gitlab"]

    def test_passes_a_file_of_headers_rules_and_comments(self):
        directory = self.workspace(CODEOWNERS=fixture("headers-rules-and-comments.codeowners"))

        self.assert_passed(self.check(directory))

    def test_fails_an_owner_gitlab_does_not_recognise(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n/docs/ platform-team\n")

        violation = self.assert_violation(
            self.check(directory), "'platform-team' is no user, group or email address"
        )

        self.assertEqual(violation["evidence"], "CODEOWNERS: 2")

    def test_fails_a_section_header_that_is_not_closed(self):
        directory = self.workspace(CODEOWNERS="* @company/platform\n[Backend\n")

        self.assert_violation(self.check(directory), "'[Backend' is no closed section header")

    def test_fails_a_default_owner_on_a_header_gitlab_does_not_recognise(self):
        directory = self.workspace(CODEOWNERS="[Backend] engineering\n/api/ @company/backend\n")

        self.assert_violation(self.check(directory), "so the section does not default to it")

    def test_skips_when_there_is_no_codeowners(self):
        self.assert_skipped(self.check(self.workspace()), "carries no CODEOWNERS file")

    def test_skips_a_repository_that_carries_no_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{".gitlab-ci.yml": "build:\n  script:\n    - make\n"})), "carries no CODEOWNERS file")


if __name__ == "__main__":
    unittest.main()
