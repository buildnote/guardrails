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

WITHOUT_VERSION = fixture("without-version.gradle.kts")

POM = fixture("pom.xml")


MODULE = "service/build.gradle.kts"


class VersionReproducibleTest(GuardrailTestCase):
    SCRIPT = "version-reproducible.py"
    COLLECT = ["java"]

    def gradle(self, manifest=TOOLCHAIN, **files):
        return self.workspace(**dict({
            "settings.gradle.kts": SETTINGS,
            "build.gradle.kts": manifest,
        }, **files))

    def test_passes_a_build_whose_toolchain_provisions_the_jdk(self):
        self.assert_passed(self.check(self.gradle()))

    def test_fails_a_build_that_declares_the_version_by_source_compatibility(self):
        directory = self.gradle(COMPATIBILITY)

        violation = self.assert_violation(
            self.check(directory),
            "build.gradle.kts declares Java 17 by compatibility rather than by a toolchain",
        )

        self.assertEqual(violation["evidence"], "build.gradle.kts (compatibility)")

    def test_fails_a_maven_build_that_declares_the_version_by_property(self):
        directory = self.workspace(**{"pom.xml": POM})

        violation = self.assert_violation(
            self.check(directory),
            "pom.xml declares Java 21 by property rather than by a toolchain",
        )

        self.assertEqual(violation["evidence"], "pom.xml (property)")

    def test_skips_a_build_that_declares_no_version_at_all(self):
        directory = self.gradle(WITHOUT_VERSION)

        self.assert_skipped(self.check(directory), "nothing in build.gradle.kts declares a Java version")

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

    def test_fails_an_included_project_that_declares_the_version_by_compatibility(self):
        directory = self.gradle(**{MODULE: COMPATIBILITY})

        violation = self.assert_violation(
            self.check(directory),
            "service/build.gradle.kts declares Java 17 by compatibility rather than by a toolchain",
        )

        self.assertEqual(violation["evidence"], "service/build.gradle.kts (compatibility)")

    def test_reports_every_project_whose_declaration_is_not_reproducible(self):
        directory = self.gradle(COMPATIBILITY, **{MODULE: COMPATIBILITY})

        result = self.check(directory)

        self.assertEqual(
            sorted(it["evidence"] for it in result.violations),
            ["build.gradle.kts (compatibility)", "service/build.gradle.kts (compatibility)"],
        )


if __name__ == "__main__":
    unittest.main()
