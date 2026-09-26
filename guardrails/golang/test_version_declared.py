#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MODULE = fixture("checksums-committed-module.mod")

WITHOUT_VERSION = fixture("without-version.mod")

WORKSPACE = fixture("version-declared-workspace.work")

SERVICE = fixture("checksums-committed-service.mod")

CLI = fixture("cli.mod")


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["golang"]

    def test_passes_a_module_that_declares_a_go_directive(self):
        self.assert_passed(self.check(self.workspace(**{"go.mod": MODULE})))

    def test_passes_a_workspace_that_declares_it_once(self):
        directory = self.workspace(**{
            "go.work": WORKSPACE,
            "service/go.mod": SERVICE,
            "cli/go.mod": CLI,
        })

        self.assert_passed(self.check(directory))

    def test_fails_a_module_that_declares_none(self):
        directory = self.workspace(**{"go.mod": WITHOUT_VERSION})

        violation = self.assert_violation(self.check(directory), "No Go version declared in go.mod")

        self.assertEqual(violation["evidence"], "go.mod")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"go.mod": MODULE.replace("go 1.22", "go 1.19")})

        violation = self.assert_violation(self.check(directory), "asks for Go 1.19, older than the 1.21 expected")

        self.assertEqual(violation["evidence"], "go.mod (Go 1.19)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"go.mod": MODULE})

        self.assert_passed(self.check(directory, minVersion="1.22"))
        self.assert_violation(self.check(directory, minVersion="1.23"), "older than the 1.23 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"go.mod": MODULE})

        self.assert_passed(self.check(directory, minVersion="1.22.0"))
        self.assert_violation(self.check(directory, minVersion="1.22.1"), "older than the 1.22.1 expected")

    def test_skips_a_directory_with_no_go_module(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Go module in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": MODULE}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"backend/go.mod": MODULE})

        self.assert_passed(self.check(directory, projectDir="backend"))


if __name__ == "__main__":
    unittest.main()
