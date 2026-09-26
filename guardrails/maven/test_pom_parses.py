#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

POM = fixture("pom-parses-pom.xml")

MODULE_POM = fixture("pom-parses-module-pom.xml")

UNCLOSED = POM.replace("</project>", "")

MODULE = "service/pom.xml"


class PomParsesTest(GuardrailTestCase):
    SCRIPT = "pom-parses.py"
    COLLECT = ["maven"]

    def build(self, **files):
        return self.workspace(**dict({"pom.xml": POM, MODULE: MODULE_POM}, **files))

    def test_passes_a_pom_that_parses(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_pom_that_does_not(self):
        directory = self.workspace(**{"pom.xml": UNCLOSED})

        violation = self.assert_violation(self.check(directory), "pom.xml is not well formed XML")

        self.assertEqual(violation["evidence"], "pom.xml")

    def test_says_what_a_malformed_pom_costs(self):
        directory = self.workspace(**{"pom.xml": UNCLOSED})

        violation = self.assert_violation(self.check(directory), "the coordinates, the properties, the modules")

        self.assertIn("are all unknown", violation["message"])

    def test_skips_a_directory_with_no_maven_build(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { kotlin(\"jvm\") }\n"})

        self.assert_skipped(self.check(directory), "no Maven build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"app/pom.xml": UNCLOSED})

        self.assert_skipped(self.check(directory), "no Maven build in .")
        self.assert_violation(self.check(directory, projectDir="app"), "pom.xml is not well formed XML")


if __name__ == "__main__":
    unittest.main()
