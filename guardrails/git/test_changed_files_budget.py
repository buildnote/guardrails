#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class ChangedFilesBudgetTest(GuardrailTestCase):
    SCRIPT = "changed-files-budget.py"
    COLLECT = ["git"]

    def test_passes_a_change_inside_the_budget(self):
        self.assert_passed(self.changing(["one.kt", "two.kt"], maxFiles="5"))

    def test_fails_a_change_over_the_budget(self):
        self.assert_violation(self.changing(["one.kt", "two.kt", "three.kt"], maxFiles="2"), "touches 3 files")

    def test_counts_the_files_it_reports(self):
        result = self.changing(["one.kt", "two.kt", "three.kt"], maxFiles="2")

        self.assertEqual(result.violations[0]["evidence"], "3 files changed")

    def test_passes_a_change_exactly_at_the_budget(self):
        self.assert_passed(self.changing(["one.kt", "two.kt"], maxFiles="2"))

    def test_leaves_out_the_files_it_is_told_to_ignore(self):
        self.assert_passed(
            self.changing(["one.kt", "yarn.lock", "generated/api.kt"], maxFiles="1", ignore="*.lock,generated/*")
        )

    def test_still_counts_files_no_glob_matches(self):
        self.assert_violation(
            self.changing(["one.kt", "two.kt", "yarn.lock"], maxFiles="1", ignore="*.lock"),
            "touches 2 files",
        )

    def test_skips_a_budget_that_is_not_a_number(self):
        self.assert_skipped(self.changing(["one.kt"], maxFiles="lots"), "is not a number")

    def test_passes_an_empty_range(self):
        directory = self.repository()

        self.assert_passed(self.check(directory, baseRef=self.head(directory)))

    def changing(self, paths, **inputs):
        directory = self.repository()
        base = self.git(directory, "rev-parse", "HEAD").strip()

        for path in paths:
            self.write(directory, path, "class Widget\n")

        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: bound the queue")

        return self.check(directory, baseRef=base, **inputs)


if __name__ == "__main__":
    unittest.main()
