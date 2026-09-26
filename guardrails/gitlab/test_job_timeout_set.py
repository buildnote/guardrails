#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)


def pipeline(timeout=None, job="build"):
    declared = "  timeout: %s\n" % timeout if timeout is not None else ""

    return "%s:\n%s  script:\n    - ./gradlew check\n" % (job, declared)


TRIGGERS = fixture("triggers.yml")


class JobTimeoutSetTest(GuardrailTestCase):
    SCRIPT = "job-timeout-set.py"
    COLLECT = ["gitlab"]

    def gitlab(self, text, **inputs):
        return self.check(self.workspace(**{".gitlab-ci.yml": text}), **inputs)

    def test_passes_a_job_that_declares_a_timeout(self):
        self.assert_passed(self.gitlab(pipeline(timeout="15 minutes")))

    def test_fails_a_job_that_declares_none(self):
        self.assert_violation(self.gitlab(pipeline()), "declares no timeout")

    def test_fails_a_timeout_over_the_longest_accepted(self):
        self.assert_violation(self.gitlab(pipeline(timeout="3 hours")), "may run for 3 hours, over the 60 minutes")

    def test_honours_the_longest_it_is_given(self):
        self.assert_passed(self.gitlab(pipeline(timeout="3 hours"), maxMinutes="240"))

    def test_reads_the_duration_the_way_gitlab_writes_it(self):
        self.assert_passed(self.gitlab(pipeline(timeout="1h 30m"), maxMinutes="120"))
        self.assert_violation(self.gitlab(pipeline(timeout="1h 30m")), "over the 60 minutes")

    def test_passes_a_duration_it_cannot_read_rather_than_guessing_at_it(self):
        self.assert_passed(self.gitlab(pipeline(timeout="a fortnight")))

    def test_passes_a_job_that_only_triggers_a_downstream_pipeline(self):
        self.assert_passed(self.gitlab(TRIGGERS))

    def test_names_the_job_it_found(self):
        result = self.gitlab(pipeline(job="deploy"))

        self.assertIn("deploy", result.violations[0]["evidence"])

    def test_skips_a_timeout_that_is_not_a_number(self):
        self.assert_skipped(self.gitlab(pipeline(timeout="15 minutes"), maxMinutes="ages"), "is not a number")

    def test_skips_a_repository_with_no_pipeline(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "carries no GitLab CI file")

    def test_skips_a_repository_that_carries_only_a_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{"CODEOWNERS": "* @company/platform\n"})), "carries no GitLab CI file")


if __name__ == "__main__":
    unittest.main()
