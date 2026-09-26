#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

WORKFLOW = ".github/workflows/pr.yml"

INJECTED = fixture("injected.yml")

THROUGH_THE_ENVIRONMENT = fixture("through-the-environment.yml")

TRUSTED = fixture("trusted.yml")

BRANCH_NAME = fixture("branch-name.yml")

SPACED = fixture("spaced.yml")


class NoScriptInjectionTest(GuardrailTestCase):
    SCRIPT = "no-script-injection.py"
    COLLECT = ["github"]

    def workflow(self, definition):
        return self.workspace(**{WORKFLOW: definition})

    def test_fails_an_untrusted_expression_in_a_shell_body(self):
        violation = self.assert_violation(
            self.check(self.workflow(INJECTED)), "interpolates github.event.pull_request.title into the shell body"
        )

        self.assertIn("greet", violation["evidence"])

    def test_passes_the_same_value_through_the_environment(self):
        self.assert_passed(self.check(self.workflow(THROUGH_THE_ENVIRONMENT)))

    def test_passes_an_expression_nobody_outside_controls(self):
        self.assert_passed(self.check(self.workflow(TRUSTED)))

    def test_fails_a_branch_name(self):
        self.assert_violation(self.check(self.workflow(BRANCH_NAME)), "interpolates github.head_ref")

    def test_reads_an_expression_whatever_it_is_spaced_like(self):
        self.assert_violation(self.check(self.workflow(SPACED)), "interpolates github.event.issue.title")

    def test_honours_the_expressions_it_is_given(self):
        self.assert_passed(self.check(self.workflow(INJECTED), expressions="github.event.comment.body"))

    def test_skips_a_repository_with_no_workflow(self):
        self.assert_skipped(self.check(self.workspace()), "carries no GitHub Actions workflow")

    def test_skips_a_repository_that_carries_only_a_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{"CODEOWNERS": "* @company/platform\n"})), "carries no GitHub Actions workflow")


if __name__ == "__main__":
    unittest.main()
