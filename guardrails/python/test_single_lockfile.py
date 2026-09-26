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

POETRY_LOCK = fixture("poetry.lock")


class SingleLockfileTest(GuardrailTestCase):
    SCRIPT = "single-lockfile.py"
    COLLECT = ["python"]

    def test_passes_a_project_that_commits_one(self):
        directory = self.workspace(**{"pyproject.toml": PYPROJECT, "uv.lock": UV_LOCK})

        self.assert_passed(self.check(directory))

    def test_passes_a_project_that_commits_none(self):
        self.assert_passed(self.check(self.workspace(**{"pyproject.toml": PYPROJECT})))

    def test_fails_a_project_that_commits_two(self):
        directory = self.workspace(**{
            "pyproject.toml": PYPROJECT,
            "uv.lock": UV_LOCK,
            "poetry.lock": POETRY_LOCK,
        })

        violation = self.assert_violation(self.check(directory), "commits 2 lock files")

        self.assertEqual(violation["evidence"], "poetry.lock, uv.lock")

    def test_skips_a_directory_with_no_python_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Python project in .")


if __name__ == "__main__":
    unittest.main()
