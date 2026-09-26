#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

SETTINGS = "rootProject.name = \"widget\"\n\ninclude(\"service\")\n"

TOOLCHAIN = fixture("toolchain.gradle.kts")

COMPATIBILITY = fixture("compatibility.gradle.kts")

LEGACY = fixture("legacy.gradle.kts")

RELEASE = fixture("release.gradle.kts")

COMMENTED = fixture("commented.gradle.kts")

POM = fixture("pom.xml")


class JavaTest(CollectorTestCase):
    COLLECTOR = "java"

    def gradle(self, manifest=TOOLCHAIN, **files):
        return self.workspace(**dict({
            "settings.gradle.kts": SETTINGS,
            "build.gradle.kts": manifest,
        }, **files))

    def test_reads_the_version_a_toolchain_selects(self):
        facts = self.collect(self.gradle())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertIn("build.gradle.kts", facts["sources"])
        self.assertEqual(
            facts["declared"],
            {"version": "21", "source": "build.gradle.kts", "mechanism": "toolchain", "reproducible": True},
        )
        self.assertTrue(facts["toolchain"])

    def test_reads_source_compatibility_as_a_mechanism_that_is_not_reproducible(self):
        facts = self.collect(self.gradle(COMPATIBILITY))

        self.assertEqual(
            facts["declared"],
            {"version": "17", "source": "build.gradle.kts", "mechanism": "compatibility", "reproducible": False},
        )
        self.assertFalse(facts["toolchain"])

    def test_reads_a_legacy_version_as_the_release_it_names(self):
        self.assertEqual(self.collect(self.gradle(LEGACY))["declared"]["version"], "8")

    def test_reads_the_release_the_compiler_is_given(self):
        facts = self.collect(self.gradle(RELEASE))

        self.assertEqual(facts["declared"]["mechanism"], "release")
        self.assertEqual(facts["declared"]["version"], "21")
        self.assertFalse(facts["declared"]["reproducible"])

    def test_leaves_a_commented_out_declaration_out(self):
        self.assertEqual(self.collect(self.gradle(COMMENTED))["declared"]["version"], "17")

    def test_reads_the_version_each_included_project_declares(self):
        facts = self.collect(self.gradle(**{"service/build.gradle.kts": COMPATIBILITY}))

        self.assertEqual(
            [(it["path"], it["directory"], (it["declared"] or {}).get("version")) for it in facts["projects"]],
            [(":", ".", "21"), (":service", "service", "17")],
        )

    def test_says_a_project_declaring_nothing_declares_nothing(self):
        facts = self.collect(self.gradle(**{"service/build.gradle.kts": "plugins {\n    java\n}\n"}))

        self.assertIsNone(facts["projects"][1]["declared"])

    def test_reads_a_maven_property_when_gradle_declares_nothing(self):
        facts = self.collect(self.workspace(**{"pom.xml": POM}))

        self.assertEqual(
            facts["declared"],
            {"version": "21", "source": "pom.xml", "mechanism": "property", "reproducible": False},
        )
        self.assertEqual(facts["sources"], ["pom.xml"])
        self.assertEqual(facts["projects"], [])

    def test_prefers_gradle_over_maven(self):
        facts = self.collect(self.gradle(**{"pom.xml": POM}))

        self.assertEqual(facts["declared"]["source"], "build.gradle.kts")

    def test_collects_nothing_where_there_is_no_gradle_or_maven_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"README.md": "widget\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(**{"build.gradle.kts": TOOLCHAIN}), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"backend/build.gradle.kts": TOOLCHAIN})
        facts = self.collect(directory, projectDir="backend")

        self.assertEqual(facts["directory"], "backend")
        self.assertEqual(facts["declared"]["version"], "21")


if __name__ == "__main__":
    unittest.main()
