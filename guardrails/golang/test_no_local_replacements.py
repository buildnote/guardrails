#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MODULE = fixture("no-local-replacements-module.mod")

SUM = "github.com/spf13/cobra v1.8.1/go.mod h1:wHxEcudfqmLYa8iTfL+OuZPbBZkmvliBWKIezN3kD9Y=\n"

WORKSPACE = fixture("no-local-replacements-workspace.work")

SERVICE = fixture("no-local-replacements-service.mod")


class NoLocalReplacementsTest(GuardrailTestCase):
    SCRIPT = "no-local-replacements.py"
    COLLECT = ["golang"]

    def module(self, *replacements):
        return self.workspace(**{"go.mod": MODULE + "".join(replacements), "go.sum": SUM})

    def test_passes_a_module_that_replaces_nothing(self):
        self.assert_passed(self.check(self.module()))

    def test_passes_a_replacement_to_another_module_path(self):
        directory = self.module("\nreplace github.com/company/queue => github.com/company/queue/v2 v2.1.0\n")

        self.assert_passed(self.check(directory))

    def test_fails_a_replacement_to_a_directory_inside_the_checkout(self):
        directory = self.module("\nreplace github.com/company/queue => ./internal/queue\n")

        violation = self.assert_violation(
            self.check(directory),
            "go.mod replaces github.com/company/queue with the directory ./internal/queue",
        )

        self.assertEqual(violation["evidence"], "go.mod (github.com/company/queue => ./internal/queue)")

    def test_fails_a_replacement_to_a_directory_beside_the_checkout(self):
        directory = self.module("\nreplace github.com/company/queue v1.4.0 => ../queue\n")

        self.assert_violation(self.check(directory), "with the directory ../queue")

    def test_fails_a_replacement_to_an_absolute_path(self):
        directory = self.module("\nreplace github.com/company/queue => /opt/src/queue\n")

        self.assert_violation(self.check(directory), "with the directory /opt/src/queue")

    def test_fails_a_replacement_to_a_windows_path(self):
        directory = self.module("\nreplace github.com/company/queue => C:\\src\\queue\n")

        self.assert_violation(self.check(directory), "with the directory C:\\src\\queue")

    def test_fails_a_replacement_a_workspace_declares(self):
        directory = self.workspace(**{
            "go.work": WORKSPACE,
            "service/go.mod": SERVICE,
            "service/go.sum": SUM,
        })

        violation = self.assert_violation(self.check(directory), "with the directory ../queue")

        self.assertEqual(violation["evidence"], "go.work (github.com/company/queue => ../queue)")

    def test_reports_every_local_replacement(self):
        directory = self.module(
            "\nreplace github.com/company/queue => ./internal/queue\n",
            "\nreplace github.com/company/cache => ../cache\n",
        )

        result = self.check(directory)

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            ["go.mod (github.com/company/queue => ./internal/queue)", "go.mod (github.com/company/cache => ../cache)"],
        )
        self.assertEqual(result.code, 1)

    def test_skips_a_directory_with_no_go_module(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Go module in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.module(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "backend/go.mod": MODULE + "\nreplace github.com/company/queue => ./internal/queue\n",
        })

        self.assert_violation(self.check(directory, projectDir="backend"), "with the directory ./internal/queue")


if __name__ == "__main__":
    unittest.main()
