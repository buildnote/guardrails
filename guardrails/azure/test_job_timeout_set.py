#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def pipeline(timeout=None, job="build"):
    declared = "    timeoutInMinutes: %s\n" % timeout if timeout is not None else ""

    return "jobs:\n  - job: %s\n%s    steps:\n      - script: ./gradlew check\n" % (job, declared)


TEMPLATED = """jobs:
  - template: jobs/build.yml
"""

STEPS_ONLY = """steps:
  - script: ./gradlew check
"""


class JobTimeoutSetTest(GuardrailTestCase):
    SCRIPT = "job-timeout-set.py"
    COLLECT = ["azure"]

    def azure(self, text, **inputs):
        return self.check(self.workspace(**{"azure-pipelines.yml": text}), **inputs)

    def test_passes_a_job_that_declares_a_timeout(self):
        self.assert_passed(self.azure(pipeline(timeout=15)))

    def test_fails_a_job_that_declares_none(self):
        self.assert_violation(self.azure(pipeline()), "declares no timeout")

    def test_fails_a_job_that_asks_for_the_maximum(self):
        self.assert_violation(self.azure(pipeline(timeout=0)), "asks for the maximum timeout")

    def test_fails_a_timeout_over_the_longest_accepted(self):
        self.assert_violation(self.azure(pipeline(timeout=180)), "may run for 180 minutes, over the 60")

    def test_honours_the_longest_it_is_given(self):
        self.assert_passed(self.azure(pipeline(timeout=180), maxMinutes="240"))

    def test_passes_a_job_that_comes_from_a_template(self):
        self.assert_passed(self.azure(TEMPLATED))

    def test_names_a_pipeline_written_as_bare_steps(self):
        result = self.azure(STEPS_ONLY)

        self.assertIn("the only job", result.violations[0]["evidence"])

    def test_names_the_job_it_found(self):
        result = self.azure(pipeline(job="deploy"))

        self.assertIn("deploy", result.violations[0]["evidence"])

    def test_skips_a_timeout_that_is_not_a_number(self):
        self.assert_skipped(self.azure(pipeline(timeout=15), maxMinutes="ages"), "is not a number")

    def test_skips_a_repository_with_no_pipeline(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "no Azure Pipelines definition")


if __name__ == "__main__":
    unittest.main()
