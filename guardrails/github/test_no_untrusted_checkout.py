#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"

DANGEROUS = fixture("dangerous.yml") % SHA

SAFE_TARGET = fixture("safe-target.yml") % SHA

TRUSTED_TRIGGER = fixture("trusted-trigger.yml") % SHA

WORKFLOW_RUN = fixture("workflow-run.yml") % SHA


RUNS_HEAD = fixture("runs-head.yml") % SHA


class NoUntrustedCheckoutTest(GuardrailTestCase):
    SCRIPT = "no-untrusted-checkout.py"
    COLLECT = ["github"]

    def pipeline(self, text, **inputs):
        return self.check(self.workspace(**{".github/workflows/build.yml": text}), **inputs)

    def test_fails_a_privileged_trigger_that_checks_out_the_request(self):
        self.assert_violation(self.pipeline(DANGEROUS), "checks out a ref of its own choosing")

    def test_names_the_trigger_it_found(self):
        result = self.pipeline(DANGEROUS)

        self.assertIn("pull_request_target", result.violations[0]["message"])

    def test_passes_a_privileged_trigger_that_checks_out_the_base(self):
        self.assert_passed(self.pipeline(SAFE_TARGET))

    def test_passes_a_trusted_trigger_that_checks_out_the_request(self):
        self.assert_passed(self.pipeline(TRUSTED_TRIGGER))

    def test_fails_a_workflow_run_trigger_that_checks_out_the_run(self):
        self.assert_violation(self.pipeline(WORKFLOW_RUN), "runs untrusted code")

    def test_fails_a_privileged_trigger_that_runs_the_requests_revision(self):
        self.assert_violation(self.pipeline(RUNS_HEAD), "passes the request's own revision into a command")

    def test_skips_a_repository_with_no_pipeline(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "carries no GitHub Actions workflow")

    def test_skips_a_repository_that_carries_only_a_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{"CODEOWNERS": "* @company/platform\n"})), "carries no GitHub Actions workflow")


if __name__ == "__main__":
    unittest.main()
