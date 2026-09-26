#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

PATHS = ".github/dependabot.yml,renovate.json"

DEPENDABOT = fixture("dependabot.yml")


class DependencyUpdatesConfiguredTest(GuardrailTestCase):
    SCRIPT = "dependency-updates-configured.py"
    COLLECT = ["files"]

    def check(self, directory, **inputs):
        inputs.setdefault("paths", PATHS)

        return GuardrailTestCase.check(self, directory, **inputs)

    def test_passes_a_repository_configured_for_dependabot(self):
        directory = self.workspace(**{".github/dependabot.yml": DEPENDABOT})

        self.assert_passed(self.check(directory))

    def test_passes_a_repository_configured_for_renovate(self):
        directory = self.workspace(**{"renovate.json": '{"extends": ["config:recommended"]}\n'})

        self.assert_passed(self.check(directory))

    def test_fails_a_repository_that_automates_none(self):
        violation = self.assert_violation(self.check(self.workspace()), "automates no dependency update")

        self.assertEqual(violation["evidence"], ".github/dependabot.yml")

    def test_honours_the_paths_it_is_given(self):
        directory = self.workspace(**{"renovate.json": '{"extends": ["config:recommended"]}\n'})

        self.assert_violation(self.check(directory, paths=".github/dependabot.yml"), "automates no dependency update")


if __name__ == "__main__":
    unittest.main()
