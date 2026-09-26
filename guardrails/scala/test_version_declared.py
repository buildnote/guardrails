#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("dependencies-pinned-build.sbt")

WITHOUT_VERSION = BUILD.replace('ThisBuild / scalaVersion := "3.4.1"\n', "")

PROPERTIES = "project/build.properties"


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["scala"]

    def build(self, **files):
        return self.workspace(**dict({"build.sbt": BUILD, PROPERTIES: "sbt.version=1.9.9\n"}, **files))

    def test_passes_a_build_that_declares_the_compiler(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_build_that_declares_none(self):
        directory = self.build(**{"build.sbt": WITHOUT_VERSION})

        violation = self.assert_violation(self.check(directory), "No Scala version declared in build.sbt")

        self.assertEqual(violation["evidence"], "build.sbt")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.build(**{"build.sbt": BUILD.replace("3.4.1", "2.12.18")})

        violation = self.assert_violation(self.check(directory), "asks for Scala 2.12.18, older than the 2.13 expected")

        self.assertEqual(violation["evidence"], "build.sbt (Scala 2.12.18)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.build()

        self.assert_passed(self.check(directory, minVersion="3.4"))
        self.assert_violation(self.check(directory, minVersion="3.5"), "older than the 3.5 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.build(**{"build.sbt": BUILD.replace("3.4.1", "2.13")})

        self.assert_passed(self.check(directory, minVersion="2.13.0"))
        self.assert_violation(self.check(directory, minVersion="2.13.1"), "older than the 2.13.1 expected")

    def test_skips_a_checkout_whose_build_file_could_not_be_read(self):
        directory = self.workspace(**{PROPERTIES: "sbt.version=1.9.9\n"})

        self.assert_skipped(self.check(directory), "build.sbt: the build file could not be read")

    def test_skips_a_directory_with_no_sbt_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no sbt build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/build.sbt": BUILD})

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
