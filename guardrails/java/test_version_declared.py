#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

SETTINGS = "rootProject.name = \"widget\"\n\ninclude(\"service\")\n"

TOOLCHAIN = fixture("toolchain.gradle.kts")

LEGACY = fixture("legacy.gradle.kts")

WITHOUT_VERSION = fixture("without-version.gradle.kts")

POM = fixture("pom.xml")


MODULE = "service/build.gradle.kts"


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["java"]

    def gradle(self, manifest=TOOLCHAIN, **files):
        return self.workspace(**dict({
            "settings.gradle.kts": SETTINGS,
            "build.gradle.kts": manifest,
        }, **files))

    def test_passes_a_gradle_build_whose_toolchain_names_a_release(self):
        self.assert_passed(self.check(self.gradle()))

    def test_passes_a_maven_build_that_sets_the_compiler_release(self):
        self.assert_passed(self.check(self.workspace(**{"pom.xml": POM})))

    def test_fails_a_build_that_declares_no_version(self):
        directory = self.gradle(WITHOUT_VERSION)

        violation = self.assert_violation(self.check(directory), "No Java version declared in build.gradle.kts")

        self.assertEqual(violation["evidence"], "build.gradle.kts")

    def test_fails_a_release_older_than_the_floor(self):
        directory = self.gradle(LEGACY)

        violation = self.assert_violation(self.check(directory), "asks for Java 8, older than the 17 expected")

        self.assertEqual(violation["evidence"], "build.gradle.kts (Java 8)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.gradle()

        self.assert_passed(self.check(directory, minVersion="21"))
        self.assert_violation(self.check(directory, minVersion="25"), "older than the 25 expected")

    def test_skips_a_directory_with_no_gradle_or_maven_build(self):
        directory = self.workspace(**{"main.go": "package main\n"})

        self.assert_skipped(self.check(directory), "no Gradle or Maven build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.gradle(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "backend/settings.gradle.kts": SETTINGS,
            "backend/build.gradle.kts": TOOLCHAIN,
        })

        self.assert_passed(self.check(directory, projectDir="backend"))

    def test_passes_a_build_where_only_an_included_project_declares_a_release(self):
        directory = self.gradle(WITHOUT_VERSION, **{MODULE: TOOLCHAIN})

        self.assert_passed(self.check(directory))

    def test_fails_an_included_project_below_the_floor(self):
        directory = self.gradle(**{MODULE: LEGACY})

        violation = self.assert_violation(self.check(directory), "asks for Java 8, older than the 17 expected")

        self.assertEqual(violation["evidence"], "service/build.gradle.kts (Java 8)")


if __name__ == "__main__":
    unittest.main()
