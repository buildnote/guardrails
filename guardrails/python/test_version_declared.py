#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

PYPROJECT = fixture("pyproject.toml")

WITHOUT_VERSION = fixture("without-version.toml")


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["python"]

    def test_passes_a_project_that_declares_requires_python(self):
        self.assert_passed(self.check(self.workspace(**{"pyproject.toml": PYPROJECT})))

    def test_passes_a_project_that_declares_a_python_version_file(self):
        directory = self.workspace(**{"pyproject.toml": WITHOUT_VERSION, ".python-version": "3.12.2\n"})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_declares_none(self):
        directory = self.workspace(**{"pyproject.toml": WITHOUT_VERSION})

        violation = self.assert_violation(self.check(directory), "No Python version declared in pyproject.toml")

        self.assertEqual(violation["evidence"], "pyproject.toml")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"pyproject.toml": PYPROJECT.replace(">=3.11", ">=3.7")})

        violation = self.assert_violation(self.check(directory), "asks for Python >=3.7, older than the 3.9 expected")

        self.assertEqual(violation["evidence"], "pyproject.toml (Python >=3.7)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"pyproject.toml": PYPROJECT})

        self.assert_passed(self.check(directory, minVersion="3.11"))
        self.assert_violation(self.check(directory, minVersion="3.12"), "older than the 3.12 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"pyproject.toml": WITHOUT_VERSION, ".python-version": "3.12\n"})

        self.assert_passed(self.check(directory, minVersion="3.12.0"))
        self.assert_violation(self.check(directory, minVersion="3.12.1"), "older than the 3.12.1 expected")

    def test_skips_a_directory_with_no_python_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.kt": "fun main() {}\n"})), "no Python project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"pyproject.toml": PYPROJECT}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"service/pyproject.toml": PYPROJECT})

        self.assert_passed(self.check(directory, projectDir="service"))


if __name__ == "__main__":
    unittest.main()
