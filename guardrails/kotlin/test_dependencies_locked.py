#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

LOCKFILE = """# This is a Gradle generated file for dependency locking.
org.jetbrains.kotlin:kotlin-stdlib:2.1.0=compileClasspath
empty=annotationProcessor
"""


class DependenciesLockedTest(GuardrailTestCase):
    SCRIPT = "dependencies-locked.py"
    COLLECT = ["gradle"]

    def test_passes_a_build_that_commits_a_lock_file(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { }\n", "gradle.lockfile": LOCKFILE})

        self.assert_passed(self.check(directory))

    def test_fails_a_build_that_commits_none(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { }\n"})

        violation = self.assert_violation(self.check(directory), "commits 0 dependency lock files")

        self.assertEqual(violation["evidence"], "0 lock files")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { }\n", "gradle.lockfile": LOCKFILE})

        self.assert_violation(self.check(directory, minLockfiles=2), "fewer than the 2 expected")

    def test_skips_a_project_that_is_not_a_gradle_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Gradle build in .")

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { }\n", "gradle.lockfile": LOCKFILE})

        self.assert_skipped(self.check(directory, minLockfiles="one"), "minLockfiles 'one' is not a number")


if __name__ == "__main__":
    unittest.main()
