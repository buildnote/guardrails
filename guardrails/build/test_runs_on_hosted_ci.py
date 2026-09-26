#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

HOSTED = fixture("hosted.env")

SELF_HOSTED = fixture("self-hosted.env")

WORKSTATION = """HOME=/home/dana
"""


class RunsOnHostedCiTest(GuardrailTestCase):
    SCRIPT = "runs-on-hosted-ci.py"
    COLLECT = ["env"]

    def check_env(self, text, **inputs):
        workspace = self.workspace(**{"ci-environment": text})

        return self.check(workspace, envFile="ci-environment", **inputs)

    def test_passes_a_hosted_runner(self):
        self.assert_passed(self.check_env(HOSTED))

    def test_passes_a_self_hosted_runner_by_default(self):
        self.assert_passed(self.check_env(SELF_HOSTED))

    def test_fails_a_workstation(self):
        self.assert_violation(
            self.check_env(WORKSTATION),
            "not running on a CI runner",
        )

    def test_fails_a_self_hosted_runner_when_the_team_does_not_trust_one(self):
        self.assert_violation(
            self.check_env(SELF_HOSTED, allowSelfHosted="false"),
            "self hosted runner",
        )

    def test_passes_a_hosted_runner_even_when_self_hosted_is_not_trusted(self):
        self.assert_passed(self.check_env(HOSTED, allowSelfHosted="false"))

    def test_names_the_runner_it_rejected(self):
        result = self.check_env(SELF_HOSTED, allowSelfHosted="false")

        self.assertEqual(result.violations[0]["evidence"], "runner=builder-07")


if __name__ == "__main__":
    unittest.main()
