#!/usr/bin/env python3
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

HOSTED_ACTIONS = fixture("hosted-actions.env")

SELF_HOSTED = fixture("self-hosted.env")

FORKED = fixture("forked.env")

GITLAB = fixture("gitlab.env")

WORKSTATION = """HOME=/home/dana
PATH=/usr/bin
"""


class EnvTest(CollectorTestCase):
    COLLECTOR = "env"

    def collect_from(self, text, name="ci-environment"):
        return self.collect(self.workspace(**{name: text}), envFile=name)

    def test_recognises_a_hosted_github_runner(self):
        facts = self.collect_from(HOSTED_ACTIONS)

        self.assertEqual(facts["provider"], "github")
        self.assertTrue(facts["ci"])
        self.assertTrue(facts["hosted"])
        self.assertEqual(facts["runner"]["os"], "Linux")
        self.assertEqual(facts["runner"]["arch"], "X64")
        self.assertEqual(facts["runner"]["name"], "GitHub Actions 4")

    def test_recognises_a_self_hosted_runner(self):
        facts = self.collect_from(SELF_HOSTED)

        self.assertFalse(facts["hosted"])
        self.assertEqual(facts["trigger"], "push")
        self.assertFalse(facts["pullRequest"])

    def test_recognises_a_pull_request_and_its_origin(self):
        facts = self.collect_from(HOSTED_ACTIONS)

        self.assertEqual(facts["trigger"], "pull_request")
        self.assertTrue(facts["pullRequest"])
        self.assertFalse(facts["fork"])

    def test_recognises_a_pull_request_from_a_fork(self):
        self.assertTrue(self.collect_from(FORKED)["fork"])

    def test_recognises_a_gitlab_pipeline(self):
        facts = self.collect_from(GITLAB)

        self.assertEqual(facts["provider"], "gitlab")
        self.assertTrue(facts["pullRequest"])
        self.assertFalse(facts["fork"])
        self.assertEqual(facts["runner"]["name"], "shared-runner-3")

    def test_reports_a_federated_identity_being_available(self):
        self.assertTrue(self.collect_from(HOSTED_ACTIONS)["oidc"])
        self.assertTrue(self.collect_from(GITLAB)["oidc"])
        self.assertFalse(self.collect_from(SELF_HOSTED)["oidc"])

    def test_recognises_a_workstation(self):
        facts = self.collect_from(WORKSTATION)

        self.assertEqual(facts["provider"], "local")
        self.assertFalse(facts["ci"])
        self.assertIsNone(facts["hosted"])
        self.assertIsNone(facts["runner"]["os"])
        self.assertIsNone(facts["trigger"])
        self.assertIsNone(facts["fork"])

    def test_names_the_variables_it_saw(self):
        variables = self.collect_from(HOSTED_ACTIONS)["variables"]

        self.assertIn("GITHUB_EVENT_NAME", variables)
        self.assertIn("RUNNER_OS", variables)

    def test_never_carries_a_credential_out_of_the_environment(self):
        facts = self.collect_from(HOSTED_ACTIONS)

        self.assertNotIn("GITHUB_TOKEN", facts["variables"])
        self.assertNotIn("ghs_notarealtoken", json.dumps(facts))

    def test_reads_the_process_environment_when_no_file_is_given(self):
        ambient = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Linux",
            "RUNNER_ARCH": "X64",
            "RUNNER_NAME": "GitHub Actions 2",
        }

        with mock.patch.dict(os.environ, ambient, clear=False):
            facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["provider"], "github")
        self.assertTrue(facts["ci"])
        self.assertTrue(facts["hosted"])
        self.assertEqual(facts["trigger"], "push")
        self.assertEqual(facts["runner"]["name"], "GitHub Actions 2")

    def test_reports_a_workstation_from_the_process_environment(self):
        ambient = dict(
            (name, None) for name in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "TF_BUILD", "BUILDKITE")
        )
        removed = dict((name, "") for name in ambient)

        with mock.patch.dict(os.environ, removed, clear=False):
            for name in ambient:
                os.environ.pop(name, None)

            facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["provider"], "local")
        self.assertFalse(facts["ci"])

    def test_reports_an_environment_file_it_cannot_read(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}), envFile="missing")

        self.assertIn("could not be read", facts["incomplete"])



if __name__ == "__main__":
    unittest.main()
