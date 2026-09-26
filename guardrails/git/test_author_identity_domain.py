#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class AuthorIdentityDomainTest(GuardrailTestCase):
    SCRIPT = "author-identity-domain.py"
    COLLECT = ["git"]

    def test_passes_an_address_on_an_allowed_domain(self):
        self.assert_passed(self.authored("dana@company.com", domains="company.com"))

    def test_passes_an_address_on_any_of_several_domains(self):
        self.assert_passed(self.authored("dana@company.co.uk", domains="company.com,company.co.uk"))

    def test_fails_a_personal_address(self):
        self.assert_violation(self.authored("dana@gmail.com", domains="company.com"), "which is not on company.com")

    def test_reports_one_violation_naming_both_roles(self):
        result = self.authored("dana@gmail.com", domains="company.com")

        self.assertEqual(len(result.violations), 1)
        self.assertIn("author and committer", result.violations[0]["evidence"])
        self.assertIn("dana@gmail.com", result.violations[0]["evidence"])

    def test_passes_a_bot_address_by_default(self):
        self.assert_passed(self.authored("dependabot[bot]@users.noreply.github.com", domains="company.com"))

    def test_fails_a_bot_address_when_bots_are_not_accepted(self):
        self.assert_violation(
            self.authored("dependabot[bot]@users.noreply.github.com", domains="company.com", allowBots="false"),
            "which is not on company.com",
        )

    def test_ignores_the_case_of_the_domain(self):
        self.assert_passed(self.authored("Dana@COMPANY.com", domains="company.com"))

    def test_accepts_a_domain_written_with_an_at(self):
        self.assert_passed(self.authored("dana@company.com", domains="@company.com"))

    def test_skips_when_no_domain_is_configured(self):
        self.assert_skipped(self.authored("dana@company.com"), "no domains are configured")

    def test_passes_an_empty_range(self):
        directory = self.repository()

        self.assert_passed(self.check(directory, baseRef=self.head(directory), domains="company.com"))

    def authored(self, address, **inputs):
        directory = self.repository()
        base = self.git(directory, "rev-parse", "HEAD").strip()
        self.git(directory, "config", "user.email", address)
        self.commit(directory, "feat: bound the queue")

        return self.check(directory, baseRef=base, **inputs)


if __name__ == "__main__":
    unittest.main()
