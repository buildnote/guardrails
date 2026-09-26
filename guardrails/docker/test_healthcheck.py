#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

PROBED = fixture("probed.Dockerfile")

UNPROBED = fixture("unprobed.Dockerfile")

STAGED = fixture("staged.Dockerfile")


class DockerfileHealthcheckTest(GuardrailTestCase):
    SCRIPT = "healthcheck.py"
    COLLECT = ["docker"]

    def test_passes_a_dockerfile_that_declares_one(self):
        self.assert_passed(self.check(self.workspace(Dockerfile=PROBED)))

    def test_fails_a_dockerfile_that_declares_none(self):
        violation = self.assert_violation(self.check(self.workspace(Dockerfile=UNPROBED)), "declares no HEALTHCHECK")

        self.assertEqual(violation["evidence"], "Dockerfile")

    def test_names_the_final_stage_of_a_multi_stage_build(self):
        self.assert_violation(self.check(self.workspace(Dockerfile=STAGED)), "its last stage (runtime)")

    def test_reads_healthcheck_none_as_none(self):
        directory = self.workspace(Dockerfile="FROM alpine@sha256:aaaa\nHEALTHCHECK NONE\n")

        self.assert_violation(self.check(directory), "declares no HEALTHCHECK")

    def test_ignores_the_dockerfiles_it_is_told_to(self):
        directory = self.workspace(**{"jobs/Dockerfile": UNPROBED})

        self.assert_violation(self.check(directory), "declares no HEALTHCHECK")
        self.assert_passed(self.check(directory, ignore="jobs/*"))

    def test_skips_a_repository_with_no_dockerfile(self):
        self.assert_skipped(self.check(self.workspace()), "no Dockerfile was collected")


if __name__ == "__main__":
    unittest.main()
