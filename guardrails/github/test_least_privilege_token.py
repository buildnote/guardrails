#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

DECLARED = fixture("declared.yml")

UNDECLARED = fixture("undeclared.yml")

PER_JOB = fixture("per-job.yml")

WRITE_ALL = fixture("write-all.yml")

JOB_WRITE_ALL = fixture("job-write-all.yml")


MIXED = fixture("mixed.yml")


class LeastPrivilegeTokenTest(GuardrailTestCase):
    SCRIPT = "least-privilege-token.py"
    COLLECT = ["github"]

    def pipeline(self, text, **inputs):
        return self.check(self.workspace(**{".github/workflows/build.yml": text}), **inputs)

    def test_passes_a_workflow_that_declares_permissions(self):
        self.assert_passed(self.pipeline(DECLARED))

    def test_passes_a_workflow_that_declares_them_on_the_job(self):
        self.assert_passed(self.pipeline(PER_JOB))

    def test_fails_a_job_that_declares_none_under_a_workflow_that_declares_none(self):
        self.assert_violation(self.pipeline(UNDECLARED), "Job build in")

    def test_names_only_the_jobs_that_are_exposed(self):
        result = self.pipeline(MIXED)

        self.assertEqual(len(result.violations), 1)
        self.assertIn("Job publish in", result.violations[0]["message"])
        self.assertNotIn("Job build in", result.violations[0]["message"])

    def test_fails_a_workflow_that_takes_write_access_to_everything(self):
        self.assert_violation(self.pipeline(WRITE_ALL), "takes write access to everything")

    def test_fails_a_job_that_takes_write_access_to_everything(self):
        self.assert_violation(self.pipeline(JOB_WRITE_ALL), "Job build in")

    def test_accepts_write_all_when_it_is_told_to(self):
        self.assert_passed(self.pipeline(WRITE_ALL, allowWriteAll="true"))

    def test_skips_a_repository_with_no_pipeline(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "carries no GitHub Actions workflow")

    def test_skips_a_repository_that_carries_only_a_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{"CODEOWNERS": "* @company/platform\n"})), "carries no GitHub Actions workflow")


if __name__ == "__main__":
    unittest.main()
