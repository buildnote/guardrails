#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class NoWipCommitsTest(GuardrailTestCase):
    SCRIPT = "no-wip-commits.py"
    COLLECT = ["git"]

    def test_passes_finished_commits(self):
        self.assert_passed(self.commits("feat: bound the queue", "fix: reject expired tokens"))

    def test_fails_a_fixup_commit(self):
        self.assert_violation(self.commits("fixup! feat: bound the queue"), "is marked fixup!")

    def test_fails_a_squash_commit(self):
        self.assert_violation(self.commits("squash! feat: bound the queue"), "is marked squash!")

    def test_fails_a_work_in_progress_commit(self):
        self.assert_violation(self.commits("WIP on the queue"), "was not meant to be merged")

    def test_ignores_a_marker_that_is_not_at_the_start(self):
        self.assert_passed(self.commits("feat: explain what a fixup! commit is"))

    def test_ignores_the_case_of_the_marker(self):
        self.assert_violation(self.commits("wip: bound the queue"), "was not meant to be merged")

    def test_honours_the_markers_it_is_given(self):
        self.assert_passed(self.commits("WIP on the queue", markers="fixup!"))
        self.assert_violation(self.commits("DRAFT: the queue", markers="DRAFT"), "is marked DRAFT")

    def test_reports_every_such_commit(self):
        result = self.commits("fixup! one", "squash! two")

        self.assertEqual(len(result.violations), 2)

    def test_passes_an_empty_range(self):
        self.assert_passed(self.commits())

    def commits(self, *messages, **inputs):
        directory = self.repository()
        base = self.git(directory, "rev-parse", "HEAD").strip()
        for message in messages:
            self.commit(directory, message)

        return self.check(directory, baseRef=base, **inputs)


if __name__ == "__main__":
    unittest.main()
