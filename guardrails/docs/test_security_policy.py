#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

POLICY = fixture("policy.md")

NO_CONTACT = fixture("no-contact.md")


class SecurityPolicyTest(GuardrailTestCase):
    SCRIPT = "security-policy.py"
    COLLECT = ["files"]

    def test_passes_a_policy_naming_an_address(self):
        self.assert_passed(self.check(self.workspace(**{"SECURITY.md": POLICY})))

    def test_passes_a_policy_naming_a_url(self):
        policy = "# Security\n\nReport at https://company.com/security.\n\nWe answer quickly.\n"

        self.assert_passed(self.check(self.workspace(**{"SECURITY.md": policy})))

    def test_fails_a_repository_with_no_policy(self):
        self.assert_violation(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "No security policy at SECURITY.md",
        )

    def test_fails_a_policy_that_is_a_stub(self):
        self.assert_violation(
            self.check(self.workspace(**{"SECURITY.md": "# Security\n"})),
            "fewer than the 3 expected",
        )

    def test_fails_a_policy_that_names_nowhere_to_report(self):
        self.assert_violation(
            self.check(self.workspace(**{"SECURITY.md": NO_CONTACT})),
            "names no email address or URL",
        )

    def test_accepts_a_policy_with_no_contact_when_told_to(self):
        self.assert_passed(self.check(self.workspace(**{"SECURITY.md": NO_CONTACT}), contact="false"))

    def test_honours_the_path_it_is_given(self):
        self.assert_passed(self.check(self.workspace(**{".github/SECURITY.md": POLICY}), path=".github/SECURITY.md"))

    def test_skips_a_minimum_that_is_not_a_number(self):
        self.assert_skipped(self.check(self.workspace(**{"SECURITY.md": POLICY}), minLines="lots"), "is not a number")


if __name__ == "__main__":
    unittest.main()
