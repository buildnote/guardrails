#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MODULE = fixture("checksums-committed-module.mod")

WITHOUT_TOOLCHAIN = fixture("without-toolchain.mod")

SUM = "github.com/spf13/cobra v1.8.1/go.mod h1:wHxEcudfqmLYa8iTfL+OuZPbBZkmvliBWKIezN3kD9Y=\n"

WORKSPACE = fixture("toolchain-pinned-workspace.work")

SERVICE = fixture("checksums-committed-service.mod")


class ToolchainPinnedTest(GuardrailTestCase):
    SCRIPT = "toolchain-pinned.py"
    COLLECT = ["golang"]

    def test_passes_a_module_that_names_its_toolchain(self):
        self.assert_passed(self.check(self.workspace(**{"go.mod": MODULE, "go.sum": SUM})))

    def test_passes_a_workspace_that_names_it(self):
        directory = self.workspace(**{
            "go.work": WORKSPACE,
            "service/go.mod": SERVICE,
            "service/go.sum": SUM,
        })

        self.assert_passed(self.check(directory))

    def test_fails_a_module_that_names_none(self):
        directory = self.workspace(**{"go.mod": WITHOUT_TOOLCHAIN, "go.sum": SUM})

        violation = self.assert_violation(self.check(directory), "go.mod pins no toolchain")

        self.assertEqual(violation["evidence"], "go.mod")

    def test_fails_a_workspace_where_no_module_names_one(self):
        directory = self.workspace(**{
            "go.work": WORKSPACE.replace("\ntoolchain go1.22.3\n", ""),
            "service/go.mod": SERVICE,
        })

        violation = self.assert_violation(self.check(directory), "go.work pins no toolchain")

        self.assertEqual(violation["evidence"], "go.work")

    def test_skips_a_directory_with_no_go_module(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Go module in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": MODULE}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"backend/go.mod": MODULE})

        self.assert_passed(self.check(directory, projectDir="backend"))


if __name__ == "__main__":
    unittest.main()
