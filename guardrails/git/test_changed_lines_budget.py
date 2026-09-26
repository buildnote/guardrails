#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class ChangedLinesBudgetTest(GuardrailTestCase):
    SCRIPT = "changed-lines-budget.py"
    COLLECT = ["git"]

    def test_passes_a_change_inside_the_budget(self):
        self.assert_passed(self.changing({"one.kt": 3, "two.kt": 4}, maxLines="10"))

    def test_fails_a_change_over_the_budget(self):
        self.assert_violation(self.changing({"one.kt": 6, "two.kt": 6}, maxLines="10"), "adds 12 lines")

    def test_counts_the_lines_it_reports(self):
        result = self.changing({"one.kt": 6, "two.kt": 6}, maxLines="10")

        self.assertEqual(result.violations[0]["evidence"], "12 lines changed")

    def test_counts_removed_lines_too(self):
        directory = self.repository()
        self.write(directory, "one.kt", "line\n" * 10)
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: add a widget")
        base = self.head(directory)

        self.write(directory, "one.kt", "line\n" * 2)
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "refactor: shrink the widget")

        self.assert_violation(self.check(directory, baseRef=base, maxLines="5"), "removes 8")

    def test_passes_a_change_exactly_at_the_budget(self):
        self.assert_passed(self.changing({"one.kt": 5, "two.kt": 5}, maxLines="10"))

    def test_leaves_out_the_lines_it_is_told_to_ignore(self):
        self.assert_passed(
            self.changing({"one.kt": 2, "yarn.lock": 400, "generated/api.kt": 300}, maxLines="10", ignore="*.lock,generated/*")
        )

    def test_still_counts_files_no_glob_matches(self):
        self.assert_violation(
            self.changing({"one.kt": 20, "yarn.lock": 400}, maxLines="10", ignore="*.lock"),
            "adds 20 lines",
        )

    def test_counts_no_lines_for_a_binary_file(self):
        directory = self.repository()
        base = self.head(directory)
        self.write(directory, "logo.bin", "\x00\x01buildnote\x00")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "chore: add a logo")

        self.assert_passed(self.check(directory, baseRef=base, maxLines="0"))

    def test_skips_a_budget_that_is_not_a_number(self):
        self.assert_skipped(self.changing({"one.kt": 1}, maxLines="lots"), "is not a number")

    def test_skips_a_base_ref_that_does_not_resolve(self):
        self.assert_skipped(
            self.check(self.repository(), baseRef="buildnote/not-a-real-ref"),
            "is not resolvable",
        )

    def test_passes_an_empty_range(self):
        directory = self.repository()

        self.assert_passed(self.check(directory, baseRef=self.head(directory)))

    def changing(self, files, **inputs):
        directory = self.repository()
        base = self.git(directory, "rev-parse", "HEAD").strip()

        for path, count in files.items():
            self.write(directory, path, "line\n" * count)

        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: bound the queue")

        return self.check(directory, baseRef=base, **inputs)


if __name__ == "__main__":
    unittest.main()
