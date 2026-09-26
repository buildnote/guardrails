#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

INNOCUOUS = fixture("innocuous.Dockerfile")

MOUNTED = fixture("mounted.Dockerfile")

BUILD_ARG = fixture("build-arg.Dockerfile")

ENVIRONMENT = fixture("environment.Dockerfile")

BOTH = fixture("both.Dockerfile")

LOWERCASE = fixture("lowercase.Dockerfile")

SIGNING_KEY = fixture("signing-key.Dockerfile")


class DockerfileNoBuildSecretsTest(GuardrailTestCase):
    SCRIPT = "no-build-secrets.py"
    COLLECT = ["docker"]

    def dockerfile(self, text, name="Dockerfile"):
        return self.workspace(**{name: text})

    def test_passes_a_dockerfile_whose_names_hold_no_credential(self):
        self.assert_passed(self.check(self.dockerfile(INNOCUOUS)))

    def test_passes_a_dockerfile_that_mounts_its_secret_instead(self):
        self.assert_passed(self.check(self.dockerfile(MOUNTED)))

    def test_fails_a_build_argument_named_like_a_credential(self):
        violation = self.assert_violation(
            self.check(self.dockerfile(BUILD_ARG)),
            "The Dockerfile Dockerfile declares the build argument NPM_TOKEN, whose name matches *TOKEN*, "
            "and an ARG is recorded in the image history",
        )

        self.assertEqual(violation["evidence"], "Dockerfile ARG NPM_TOKEN")

    def test_fails_an_environment_variable_named_like_a_credential(self):
        violation = self.assert_violation(
            self.check(self.dockerfile(ENVIRONMENT)),
            "The Dockerfile Dockerfile declares the environment variable DATABASE_PASSWORD, whose name matches "
            "*PASSWORD*, and an ENV stays in the image",
        )

        self.assertEqual(violation["evidence"], "Dockerfile ENV DATABASE_PASSWORD")

    def test_reports_the_argument_and_the_variable_separately(self):
        result = self.check(self.dockerfile(BOTH))

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            ["Dockerfile ARG NPM_TOKEN", "Dockerfile ENV NPM_TOKEN"],
        )

    def test_reads_a_name_without_regard_to_case(self):
        self.assert_violation(
            self.check(self.dockerfile(LOWERCASE)),
            "declares the build argument npm_token, whose name matches *TOKEN*",
        )

    def test_judges_only_the_patterns_it_is_given(self):
        workspace = self.dockerfile(SIGNING_KEY)

        self.assert_violation(self.check(workspace), "whose name matches *KEY*")
        self.assert_passed(self.check(workspace, patterns="*TOKEN*,*PASSWORD*"))

    def test_names_the_dockerfile_it_read(self):
        self.assert_violation(
            self.check(self.workspace(**{"services/api/Dockerfile": BUILD_ARG})),
            "The Dockerfile services/api/Dockerfile declares the build argument NPM_TOKEN",
        )

    def test_skips_when_no_pattern_is_configured(self):
        self.assert_skipped(
            self.check(self.dockerfile(BUILD_ARG), patterns=" , "),
            "no patterns are configured",
        )

    def test_skips_a_repository_with_no_dockerfile(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no Dockerfile matched",
        )


if __name__ == "__main__":
    unittest.main()
