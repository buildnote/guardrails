#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("sbt-version-pinned-build.sbt")

PROPERTIES = "project/build.properties"


class SbtVersionPinnedTest(GuardrailTestCase):
    SCRIPT = "sbt-version-pinned.py"
    COLLECT = ["scala"]

    def build(self, **files):
        return self.workspace(**dict({"build.sbt": BUILD, PROPERTIES: "sbt.version=1.9.9\n"}, **files))

    def test_passes_a_build_that_pins_the_launcher(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_build_that_commits_no_properties(self):
        directory = self.workspace(**{"build.sbt": BUILD})

        violation = self.assert_violation(self.check(directory), "pins no launcher version")

        self.assertEqual(violation["evidence"], "project/build.properties")

    def test_fails_properties_that_pin_something_else(self):
        directory = self.build(**{PROPERTIES: "sbt.color=always\n"})

        self.assert_violation(self.check(directory), "pins no launcher version in project/build.properties")

    def test_skips_a_directory_with_no_sbt_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no sbt build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "engine/build.sbt": BUILD,
            os.path.join("engine", PROPERTIES): "sbt.version=1.10.1\n",
        })

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
