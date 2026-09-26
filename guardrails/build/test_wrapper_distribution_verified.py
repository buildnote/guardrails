#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"
DISTRIBUTION = "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14-bin.zip\n"
CHECKSUM = "distributionSha256Sum=61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa\n"


class WrapperDistributionVerifiedTest(GuardrailTestCase):
    SCRIPT = "wrapper-distribution-verified.py"
    COLLECT = ["gradle"]

    def wrapped(self, properties):
        return self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: properties,
        })

    def test_passes_a_wrapper_that_pins_a_checksum(self):
        self.assert_passed(self.check(self.wrapped(DISTRIBUTION + CHECKSUM)))

    def test_fails_a_wrapper_that_pins_no_checksum(self):
        self.assert_violation(
            self.check(self.wrapped(DISTRIBUTION)),
            "pins no distributionSha256Sum",
        )

    def test_names_the_distribution_it_would_have_verified(self):
        result = self.check(self.wrapped(DISTRIBUTION))

        self.assertIn("gradle-8.14-bin.zip", result.violations[0]["message"])
        self.assertEqual(result.violations[0]["evidence"], WRAPPER_PROPERTIES)

    def test_skips_a_project_that_does_not_commit_the_wrapper(self):
        self.assert_skipped(
            self.check(self.workspace(**{"build.gradle.kts": "plugins { }\n"})),
            "does not commit the Gradle wrapper",
        )

    def test_skips_wrapper_properties_that_pin_no_distribution(self):
        self.assert_skipped(
            self.check(self.wrapped("distributionBase=GRADLE_USER_HOME\n")),
            "pins no distribution to verify",
        )

    def test_skips_a_project_that_is_not_a_gradle_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Gradle build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(), projectDir="missing"), "missing is not a directory")


if __name__ == "__main__":
    unittest.main()
