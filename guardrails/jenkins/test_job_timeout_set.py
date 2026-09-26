#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)


def pipeline(options="", stages="stage('Build') {\n            steps {\n                sh 'make'\n            }\n        }"):
    declared = "    options {\n        timeout(%s)\n    }\n" % options if options else ""

    return "pipeline {\n    agent any\n%s    stages {\n        %s\n    }\n}\n" % (declared, stages)


def stage(name, options=""):
    declared = "            options {\n                timeout(%s)\n            }\n" % options if options else ""

    return "stage('%s') {\n%s            steps {\n                sh 'make'\n            }\n        }" % (
        name, declared)


SCRIPTED = "node('linux') {\n    stage('Build') {\n        sh 'make'\n    }\n}\n"

PARALLEL = fixture("parallel.Jenkinsfile")

EXPRESSED_PARENT = fixture("expressed-parent.Jenkinsfile")

COMPUTED_TIMEOUT = fixture("computed-timeout.Jenkinsfile")

UNGUARDED_PARALLEL = fixture("unguarded-parallel.Jenkinsfile")


class JobTimeoutSetTest(GuardrailTestCase):
    SCRIPT = "job-timeout-set.py"
    COLLECT = ["jenkins"]

    def jenkinsfile(self, text, **inputs):
        return self.check(self.workspace(Jenkinsfile=text), **inputs)

    def test_passes_a_pipeline_that_declares_a_timeout(self):
        self.assert_passed(self.jenkinsfile(pipeline(options="time: 30, unit: 'MINUTES'")))

    def test_passes_when_every_stage_declares_one(self):
        self.assert_passed(self.jenkinsfile(pipeline(stages=stage("Build", options="time: 15, unit: 'MINUTES'"))))

    def test_fails_a_stage_that_declares_none(self):
        self.assert_violation(self.jenkinsfile(pipeline()), "declares no timeout, and neither does the pipeline")

    def test_fails_a_pipeline_timeout_over_the_longest_accepted(self):
        self.assert_violation(
            self.jenkinsfile(pipeline(options="time: 3, unit: 'HOURS'")),
            "may run for 180 minutes, over the 60",
        )

    def test_fails_a_stage_timeout_over_the_longest_accepted(self):
        self.assert_violation(
            self.jenkinsfile(pipeline(stages=stage("Build", options="time: 90, unit: 'MINUTES'"))),
            "Stage Build in Jenkinsfile may run for 90 minutes, over the 60",
        )

    def test_honours_the_longest_it_is_given(self):
        self.assert_passed(self.jenkinsfile(pipeline(options="time: 3, unit: 'HOURS'"), maxMinutes="240"))

    def test_names_the_stage_it_found(self):
        result = self.jenkinsfile(pipeline(stages=stage("Deploy")))

        self.assertIn("Deploy", result.violations[0]["evidence"])

    def test_passes_a_timeout_it_could_not_read_rather_than_guessing_at_it(self):
        self.assert_passed(self.jenkinsfile(pipeline(options="time: params.LIMIT, unit: 'MINUTES'")))

    def test_counts_a_parallel_branch_as_covered_by_the_stage_holding_it(self):
        self.assert_passed(self.jenkinsfile(PARALLEL))

    def test_fails_a_parallel_branch_that_nothing_covers(self):
        result = self.jenkinsfile(UNGUARDED_PARALLEL)

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            ["Jenkinsfile Verify", "Jenkinsfile Integration"],
        )

    def test_counts_a_parallel_branch_as_covered_by_an_unnamed_stage_holding_it(self):
        self.assert_passed(self.jenkinsfile(EXPRESSED_PARENT))

    def test_passes_a_pipeline_timeout_whose_argument_is_a_call(self):
        self.assert_passed(self.jenkinsfile(COMPUTED_TIMEOUT))

    def test_skips_a_scripted_pipeline_rather_than_passing_it(self):
        self.assert_skipped(self.jenkinsfile(SCRIPTED), "scripted pipeline")

    def test_skips_a_timeout_that_is_not_a_number(self):
        self.assert_skipped(self.jenkinsfile(pipeline(), maxMinutes="ages"), "is not a number")

    def test_skips_a_repository_with_no_jenkinsfile(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "no Jenkinsfile")


if __name__ == "__main__":
    unittest.main()
