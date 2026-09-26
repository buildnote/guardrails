#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class NoMergeCommitsTest(GuardrailTestCase):
    SCRIPT = "no-merge-commits.py"
    COLLECT = ["git"]

    def test_passes_a_linear_range(self):
        directory = self.repository()
        base = self.head(directory)
        self.commit(directory, "feat: add a widget")
        self.commit(directory, "fix: repair the widget")

        self.assert_passed(self.check(directory, baseRef=base))

    def test_passes_an_empty_range(self):
        directory = self.repository()

        self.assert_passed(self.check(directory, baseRef=self.head(directory)))

    def test_fails_a_merge_commit(self):
        directory = self.repository()
        base = self.head(directory)
        trunk = self.git(directory, "rev-parse", "--abbrev-ref", "HEAD").strip()

        self.git(directory, "checkout", "--quiet", "-b", "side")
        self.commit(directory, "feat: add a widget on the side")
        self.git(directory, "checkout", "--quiet", trunk)
        self.commit(directory, "fix: repair the widget on the trunk")
        self.git(directory, "merge", "--quiet", "--no-ff", "--no-edit", "side")

        violation = self.assert_violation(self.check(directory, baseRef=base), "is a merge commit")

        self.assertIn("Merge branch", violation["evidence"])
        self.assertEqual(len(violation["evidence"].split(" ")[0]), 7)

    def test_skips_when_the_base_ref_cannot_be_resolved(self):
        directory = self.repository()

        self.assert_skipped(
            self.check(directory, baseRef="buildnote/not-a-real-ref"),
            "buildnote/not-a-real-ref is not resolvable",
        )

    def test_skips_outside_a_git_repository(self):
        self.assert_skipped(self.check(self.workspace()), "not a git repository")


if __name__ == "__main__":
    unittest.main()
