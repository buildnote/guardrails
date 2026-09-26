#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

PYPROJECT = fixture("pyproject.toml")

UV_LOCK = """version = 1
requires-python = ">=3.11"
"""


class LockfileCommittedTest(GuardrailTestCase):
    SCRIPT = "lockfile-committed.py"
    COLLECT = ["python"]

    def test_passes_a_project_that_commits_a_lock_file(self):
        directory = self.workspace(**{"pyproject.toml": PYPROJECT, "uv.lock": UV_LOCK})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_commits_none(self):
        directory = self.workspace(**{"pyproject.toml": PYPROJECT})

        violation = self.assert_violation(self.check(directory), "commits no lock file")

        self.assertEqual(violation["evidence"], "pyproject.toml")

    def test_skips_a_directory_with_no_python_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Python project in .")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "service/pyproject.toml": PYPROJECT,
            "service/uv.lock": UV_LOCK,
        })

        self.assert_passed(self.check(directory, projectDir="service"))


if __name__ == "__main__":
    unittest.main()
