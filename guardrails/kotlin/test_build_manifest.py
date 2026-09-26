#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class BuildManifestTest(GuardrailTestCase):
    SCRIPT = "build-manifest.py"
    COLLECT = ["gradle", "maven"]

    def test_passes_a_gradle_kotlin_project(self):
        self.assert_passed(self.check(self.workspace(**{"build.gradle.kts": "plugins { }\n"})))

    def test_passes_a_gradle_groovy_project(self):
        self.assert_passed(self.check(self.workspace(**{"build.gradle": "plugins { }\n"})))

    def test_passes_a_maven_project(self):
        self.assert_passed(self.check(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_fails_a_project_with_no_manifest(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"main.kt": "fun main() {}\n"})),
            "No build manifest in ., expected one of build.gradle.kts, build.gradle, pom.xml",
        )

        self.assertEqual(violation["evidence"], ".")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"service/pom.xml": "<project/>\n"})

        self.assert_passed(self.check(directory, projectDir="service"))
        self.assert_violation(self.check(directory, projectDir="."), "No build manifest in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { }\n"})

        self.assert_skipped(self.check(directory, projectDir="build.gradle.kts"), "is not a directory")
        self.assert_skipped(self.check(directory, projectDir="missing"), "missing is not a directory")


if __name__ == "__main__":
    unittest.main()
