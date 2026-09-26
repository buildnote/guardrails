#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("dependencies-pinned-build.sbt")

SNAPSHOT = BUILD.replace('"org.postgresql" % "postgresql" % "42.7.3"', '"com.company" %% "queue" % "1.4.0-SNAPSHOT"')

TEST_SNAPSHOT = BUILD.replace(
    '"org.scalameta" %% "munit" % "1.0.0" % Test',
    '"com.company" %% "harness" % "0.3.0-SNAPSHOT" % Test',
)

PROPERTIES = "project/build.properties"


class NoSnapshotDependenciesTest(GuardrailTestCase):
    SCRIPT = "no-snapshot-dependencies.py"
    COLLECT = ["scala"]

    def build(self, **files):
        return self.workspace(**dict({"build.sbt": BUILD, PROPERTIES: "sbt.version=1.9.9\n"}, **files))

    def test_passes_a_build_on_released_revisions(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_snapshot_on_the_compile_classpath(self):
        directory = self.build(**{"build.sbt": SNAPSHOT})

        violation = self.assert_violation(self.check(directory), "com.company:queue is at 1.4.0-SNAPSHOT in build.sbt")

        self.assertEqual(violation["evidence"], "com.company:queue 1.4.0-SNAPSHOT (build.sbt)")

    def test_fails_a_snapshot_a_test_configuration_takes(self):
        directory = self.build(**{"build.sbt": TEST_SNAPSHOT})

        self.assert_violation(self.check(directory), "com.company:harness is at 0.3.0-SNAPSHOT")

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
        directory = self.workspace(**{"engine/build.sbt": SNAPSHOT})

        self.assert_skipped(self.check(directory), "no sbt build in .")
        self.assert_violation(self.check(directory, projectDir="engine"), "com.company:queue is at 1.4.0-SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
