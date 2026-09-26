#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

SETTINGS = "rootProject.name = \"widget\"\n\ninclude(\"service\")\n"

TOOLCHAIN = fixture("toolchain.gradle.kts")

COMPATIBILITY = fixture("compatibility.gradle.kts")

POM = fixture("pom.xml")


class ToolchainDeclaredTest(GuardrailTestCase):
    SCRIPT = "toolchain-declared.py"
    COLLECT = ["java"]

    def gradle(self, manifest=TOOLCHAIN, **files):
        return self.workspace(**dict({
            "settings.gradle.kts": SETTINGS,
            "build.gradle.kts": manifest,
        }, **files))

    def test_passes_a_build_that_declares_a_toolchain(self):
        self.assert_passed(self.check(self.gradle()))

    def test_passes_a_build_where_an_included_project_declares_one(self):
        directory = self.gradle(COMPATIBILITY, **{"service/build.gradle.kts": TOOLCHAIN})

        self.assert_passed(self.check(directory))

    def test_fails_a_build_that_only_sets_source_compatibility(self):
        directory = self.gradle(COMPATIBILITY)

        violation = self.assert_violation(self.check(directory), "No Java toolchain is declared in build.gradle.kts")

        self.assertEqual(violation["evidence"], "build.gradle.kts")

    def test_fails_a_maven_build_that_only_sets_the_compiler_release(self):
        directory = self.workspace(**{"pom.xml": POM})

        violation = self.assert_violation(self.check(directory), "No Java toolchain is declared in pom.xml")

        self.assertEqual(violation["evidence"], "pom.xml")

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


if __name__ == "__main__":
    unittest.main()
