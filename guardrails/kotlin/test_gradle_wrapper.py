#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"
DISTRIBUTION = "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14-bin.zip\n"


class GradleWrapperTest(GuardrailTestCase):
    SCRIPT = "gradle-wrapper.py"
    COLLECT = ["gradle"]

    def test_passes_a_committed_wrapper(self):
        self.assert_passed(self.check(self.wrapped()))

    def test_fails_a_gradle_build_with_no_wrapper(self):
        result = self.check(self.workspace(**{"build.gradle.kts": "plugins { }\n"}))

        self.assertEqual(result.code, 1)
        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            ["gradlew", WRAPPER_PROPERTIES],
        )

    def test_passes_a_module_taking_the_wrapper_of_the_root_of_its_build(self):
        root = self.wrapped()
        self.write(root, "settings.gradle.kts", 'include("service")\n')
        self.write(root, "service/build.gradle.kts", "plugins { }\n")
        self.rooted_at(root)

        self.assert_passed(self.check(os.path.join(root, "service")))

    def test_fails_a_wrapper_script_that_is_not_committed(self):
        directory = self.wrapped()
        os.remove(os.path.join(directory, "gradlew"))

        self.assert_violation(self.check(directory), "Gradle wrapper file gradlew is not committed")

    def test_fails_wrapper_properties_that_pin_no_distribution(self):
        directory = self.wrapped()
        self.write(directory, WRAPPER_PROPERTIES, "distributionBase=GRADLE_USER_HOME\n")

        self.assert_violation(self.check(directory), "declares no distributionUrl, so the Gradle version is not pinned")

    def test_recognises_a_settings_only_gradle_build(self):
        result = self.check(self.workspace(**{"settings.gradle.kts": "rootProject.name = \"widget\"\n"}))

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            ["gradlew", WRAPPER_PROPERTIES],
        )

    def test_skips_a_project_that_is_not_a_gradle_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Gradle build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.wrapped("service")

        self.assert_passed(self.check(directory, projectDir="service"))
        self.assert_skipped(self.check(directory, projectDir="."), "no Gradle build in .")

    def wrapped(self, project_dir=""):
        return self.workspace(**{
            os.path.join(project_dir, "build.gradle.kts"): "plugins { }\n",
            os.path.join(project_dir, "gradlew"): "#!/bin/sh\n",
            os.path.join(project_dir, WRAPPER_PROPERTIES): DISTRIBUTION,
        })


if __name__ == "__main__":
    unittest.main()
