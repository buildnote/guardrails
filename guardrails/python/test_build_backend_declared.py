#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

PYPROJECT = fixture("pyproject.toml")

WITHOUT_BACKEND = fixture("without-backend.toml")


class BuildBackendDeclaredTest(GuardrailTestCase):
    SCRIPT = "build-backend-declared.py"
    COLLECT = ["python"]

    def test_passes_a_project_that_names_its_backend(self):
        self.assert_passed(self.check(self.workspace(**{"pyproject.toml": PYPROJECT})))

    def test_fails_a_project_that_names_none(self):
        directory = self.workspace(**{"pyproject.toml": WITHOUT_BACKEND})

        violation = self.assert_violation(self.check(directory), "declares no build backend")

        self.assertEqual(violation["evidence"], "pyproject.toml")

    def test_skips_a_checkout_that_only_lists_requirements(self):
        directory = self.workspace(**{"requirements.txt": "httpx>=0.27\n"})

        self.assert_skipped(self.check(directory), "declares requirements rather than a package to build")

    def test_skips_a_directory_with_no_python_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Python project in .")


if __name__ == "__main__":
    unittest.main()
