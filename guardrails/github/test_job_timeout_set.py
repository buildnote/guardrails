#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def workflow(timeout=None, job="build"):
    declared = "    timeout-minutes: %s\n" % timeout if timeout is not None else ""

    return "name: build\non: push\njobs:\n  %s:\n    runs-on: ubuntu-latest\n%s    steps:\n      - run: ./gradlew build\n" % (
        job, declared)


class JobTimeoutSetTest(GuardrailTestCase):
    SCRIPT = "job-timeout-set.py"
    COLLECT = ["github"]

    def pipeline(self, text, **inputs):
        return self.check(self.workspace(**{".github/workflows/build.yml": text}), **inputs)

    def test_passes_a_job_that_declares_a_timeout(self):
        self.assert_passed(self.pipeline(workflow(timeout=15)))

    def test_fails_a_job_that_declares_none(self):
        self.assert_violation(self.pipeline(workflow()), "declares no timeout")

    def test_fails_a_timeout_over_the_longest_accepted(self):
        self.assert_violation(self.pipeline(workflow(timeout=180)), "may run for 180 minutes, over the 60")

    def test_honours_the_longest_it_is_given(self):
        self.assert_passed(self.pipeline(workflow(timeout=180), maxMinutes="240"))

    def test_names_the_job_it_found(self):
        result = self.pipeline(workflow(job="deploy"))

        self.assertIn("deploy", result.violations[0]["evidence"])

    def test_skips_a_timeout_that_is_not_a_number(self):
        self.assert_skipped(self.pipeline(workflow(timeout=15), maxMinutes="ages"), "is not a number")

    def test_skips_a_repository_with_no_pipeline(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "carries no GitHub Actions workflow")

    def test_skips_a_repository_that_carries_only_a_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{"CODEOWNERS": "* @company/platform\n"})), "carries no GitHub Actions workflow")


if __name__ == "__main__":
    unittest.main()
