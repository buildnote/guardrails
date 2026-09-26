#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

LIBS_VERSIONS = "gradle/libs.versions.toml"


class KotlinVersionPinnedTest(GuardrailTestCase):
    SCRIPT = "kotlin-version-pinned.py"
    COLLECT = ["kotlin"]

    def test_passes_a_version_pinned_in_the_kotlin_dsl(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n'})

        self.assert_passed(self.check(directory))

    def test_passes_a_version_pinned_by_plugin_id(self):
        directory = self.workspace(**{
            "build.gradle.kts": 'plugins { id("org.jetbrains.kotlin.jvm") version "2.1.0" }\n'
        })

        self.assert_passed(self.check(directory))

    def test_passes_a_version_pinned_in_the_groovy_dsl(self):
        directory = self.workspace(**{
            "build.gradle": "plugins { id 'org.jetbrains.kotlin.jvm' version '2.0.20' }\n"
        })

        self.assert_passed(self.check(directory))

    def test_passes_a_version_pinned_in_a_version_catalog(self):
        directory = self.workspace(**{LIBS_VERSIONS: '[versions]\nkotlin = "2.0.0"\n'})

        self.assert_passed(self.check(directory))

    def test_passes_a_module_taking_the_version_the_root_of_its_build_declares(self):
        root = self.workspace(**{
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
            "service/build.gradle.kts": "plugins { }\n",
        })
        self.rooted_at(root)

        self.assert_passed(self.check(os.path.join(root, "service")))

    def test_fails_a_module_whose_build_declares_no_version_anywhere(self):
        root = self.workspace(**{
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": "plugins { }\n",
            "service/build.gradle.kts": "plugins { }\n",
        })
        self.rooted_at(root)

        self.assert_violation(self.check(os.path.join(root, "service")), "No Kotlin version declared in")

    def test_passes_a_version_pinned_in_a_maven_build(self):
        directory = self.workspace(**{"pom.xml": "<project><properties><kotlin.version>2.0.0</kotlin.version></properties></project>\n"})

        self.assert_passed(self.check(directory))

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "1.6.21" }\n'})

        violation = self.assert_violation(
            self.check(directory),
            "build.gradle.kts pins Kotlin 1.6.21, older than the 1.8 expected",
        )

        self.assertEqual(violation["evidence"], "build.gradle.kts (Kotlin 1.6.21)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n'})

        self.assert_passed(self.check(directory, minVersion="2.0"))
        self.assert_violation(self.check(directory, minVersion="2.1"), "older than the 2.1 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "1.9" }\n'})

        self.assert_passed(self.check(directory, minVersion="1.9.0"))
        self.assert_violation(self.check(directory, minVersion="1.9.1"), "older than the 1.9.1 expected")

    def test_compares_versions_component_by_component(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "1.10.0" }\n'})

        self.assert_passed(self.check(directory, minVersion="1.9.0"))

    def test_ignores_qualifiers_on_a_version(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0-Beta1" }\n'})

        self.assert_passed(self.check(directory, minVersion="2.0"))

    def test_fails_a_build_that_declares_no_version(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { java }\n"})

        violation = self.assert_violation(self.check(directory), "No Kotlin version declared in build.gradle.kts")

        self.assertEqual(violation["evidence"], "build.gradle.kts")

    def test_names_every_build_file_it_read(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { java }\n",
            LIBS_VERSIONS: "[versions]\njunit = \"5.11.0\"\n",
        })

        self.assert_violation(self.check(directory), "No Kotlin version declared in build.gradle.kts, gradle/libs.versions.toml")

    def test_skips_a_project_with_no_build(self):
        self.assert_skipped(self.check(self.workspace(**{"main.kt": "fun main() {}\n"})), "no Gradle or Maven build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "service/build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n'
        })

        self.assert_passed(self.check(directory, projectDir="service"))
        self.assert_skipped(self.check(directory, projectDir="."), "no Gradle or Maven build in .")


if __name__ == "__main__":
    unittest.main()
