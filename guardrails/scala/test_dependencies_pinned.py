#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("dependencies-pinned-build.sbt")

REFERENCED = BUILD.replace('"org.postgresql" % "postgresql" % "42.7.3"', '"com.company" %% "queue" % queueVersion')

MOVING = BUILD.replace('"org.postgresql" % "postgresql" % "42.7.3"', '"com.company" %% "queue" % "latest.integration"')

PROPERTIES = "project/build.properties"


class DependenciesPinnedTest(GuardrailTestCase):
    SCRIPT = "dependencies-pinned.py"
    COLLECT = ["scala"]

    def build(self, **files):
        return self.workspace(**dict({"build.sbt": BUILD, PROPERTIES: "sbt.version=1.9.9\n"}, **files))

    def test_passes_a_build_whose_every_revision_is_a_literal(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_revision_taken_from_a_reference(self):
        directory = self.build(**{"build.sbt": REFERENCED})

        violation = self.assert_violation(self.check(directory), "takes its revision from a reference")

        self.assertEqual(violation["evidence"], "com.company:queue (build.sbt)")

    def test_fails_a_moving_revision(self):
        directory = self.build(**{"build.sbt": MOVING})

        violation = self.assert_violation(self.check(directory), "is declared at latest.integration")

        self.assertEqual(violation["evidence"], "com.company:queue (build.sbt)")

    def test_says_the_dependency_list_it_read_is_a_floor(self):
        result = self.check(self.build())

        self.assertIn("read 4 library dependencies", result.output)
        self.assertIn("build.sbt: Scala read by pattern rather than a declaration", result.output)

    def test_skips_a_checkout_whose_build_file_could_not_be_read(self):
        directory = self.workspace(**{PROPERTIES: "sbt.version=1.9.9\n"})

        self.assert_skipped(self.check(directory), "build.sbt: the build file could not be read")

    def test_skips_a_directory_with_no_sbt_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no sbt build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/build.sbt": REFERENCED})

        self.assert_skipped(self.check(directory), "no sbt build in .")
        self.assert_violation(
            self.check(directory, projectDir="engine"),
            "com.company:queue in %s" % "engine/build.sbt",
        )


if __name__ == "__main__":
    unittest.main()
