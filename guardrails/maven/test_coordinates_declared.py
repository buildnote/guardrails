#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

POM = fixture("coordinates-declared-pom.xml")

INHERITING = fixture("inheriting.xml")

WITHOUT_VERSION = POM.replace("  <version>1.4.0</version>\n", "")

WITHOUT_GROUP_OR_VERSION = WITHOUT_VERSION.replace("  <groupId>io.company</groupId>\n", "")


class CoordinatesDeclaredTest(GuardrailTestCase):
    SCRIPT = "coordinates-declared.py"
    COLLECT = ["maven"]

    def test_passes_a_pom_that_names_all_three(self):
        self.assert_passed(self.check(self.workspace(**{"pom.xml": POM})))

    def test_passes_a_pom_that_inherits_the_group_and_the_version(self):
        self.assert_passed(self.check(self.workspace(**{"pom.xml": INHERITING})))

    def test_logs_what_the_build_publishes(self):
        result = self.check(self.workspace(**{"pom.xml": POM}))

        self.assertIn("publishes io.company:widget:1.4.0", result.output)

    def test_fails_a_pom_that_names_no_version(self):
        directory = self.workspace(**{"pom.xml": WITHOUT_VERSION})

        violation = self.assert_violation(self.check(directory), "pom.xml declares no version")

        self.assertEqual(violation["evidence"], "pom.xml")

    def test_names_every_coordinate_that_is_missing(self):
        directory = self.workspace(**{"pom.xml": WITHOUT_GROUP_OR_VERSION})

        self.assert_violation(self.check(directory), "declares no groupId and version")

    def test_skips_a_pom_that_could_not_be_parsed(self):
        directory = self.workspace(**{"pom.xml": POM.replace("</project>", "")})

        self.assert_skipped(self.check(directory), "could not be parsed")

    def test_skips_a_directory_with_no_maven_build(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { kotlin(\"jvm\") }\n"})

        self.assert_skipped(self.check(directory), "no Maven build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"pom.xml": POM})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"app/pom.xml": WITHOUT_VERSION})

        self.assert_skipped(self.check(directory), "no Maven build in .")
        self.assert_violation(self.check(directory, projectDir="app"), "declares no version")


if __name__ == "__main__":
    unittest.main()
