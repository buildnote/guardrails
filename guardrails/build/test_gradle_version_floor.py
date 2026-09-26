#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"


def distribution(version):
    return "distributionUrl=https\\://services.gradle.org/distributions/gradle-%s-bin.zip\n" % version


class GradleVersionFloorTest(GuardrailTestCase):
    SCRIPT = "gradle-version-floor.py"
    COLLECT = ["gradle"]

    def wrapped(self, version):
        return self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: distribution(version),
        })

    def test_passes_a_wrapper_at_the_floor(self):
        self.assert_passed(self.check(self.wrapped("8.0")))

    def test_passes_a_wrapper_above_the_floor(self):
        self.assert_passed(self.check(self.wrapped("9.7.0")))

    def test_fails_a_wrapper_below_the_floor(self):
        violation = self.assert_violation(self.check(self.wrapped("7.6.4")), "older than the 8.0 expected")

        self.assertEqual(violation["evidence"], "Gradle 7.6.4")

    def test_honours_the_floor_it_is_given(self):
        directory = self.wrapped("8.14")

        self.assert_passed(self.check(directory, minVersion="8.14"))
        self.assert_violation(self.check(directory, minVersion="9.0"), "older than the 9.0 expected")

    def test_skips_a_wrapper_that_names_no_version(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: "distributionBase=GRADLE_USER_HOME\n",
        })

        self.assert_skipped(self.check(directory), "names no Gradle version")

    def test_skips_a_project_that_is_not_a_gradle_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Gradle build in .")


if __name__ == "__main__":
    unittest.main()
