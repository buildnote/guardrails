#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class WorkItemReferenceTest(GuardrailTestCase):
    SCRIPT = "work-item-reference.py"
    COLLECT = ["git"]

    def test_passes_a_reference_in_the_subject(self):
        self.assert_passed(self.commits("feat: bound the queue COMPANY-1423"))

    def test_passes_a_reference_in_the_body(self):
        self.assert_passed(self.commits("feat: bound the queue\n\nRefs: COMPANY-1423"))

    def test_fails_a_commit_that_references_nothing(self):
        self.assert_violation(self.commits("feat: bound the queue"), "references no work item")

    def test_reports_every_commit_that_references_nothing(self):
        result = self.commits("feat: one", "feat: two")

        self.assertEqual(len(result.violations), 2)

    def test_passes_when_the_branch_carries_the_reference(self):
        self.assert_passed(self.commits("feat: bound the queue", branch="feature/COMPANY-1423-queue"))

    def test_fails_when_the_branch_carries_it_but_branches_are_not_accepted(self):
        self.assert_violation(
            self.commits("feat: bound the queue", branch="feature/COMPANY-1423-queue", allowBranch="false"),
            "references no work item",
        )

    def test_honours_the_pattern_it_is_given(self):
        self.assert_passed(self.commits("feat: bound the queue (#417)", pattern="#[0-9]+"))
        self.assert_violation(self.commits("feat: bound the queue COMPANY-1423", pattern="#[0-9]+"), "references no work item")

    def test_skips_a_pattern_that_is_not_a_regular_expression(self):
        self.assert_skipped(self.commits("feat: one", pattern="COMPANY-(["), "is not a regular expression")

    def test_passes_an_empty_range(self):
        self.assert_passed(self.commits())

    def commits(self, *messages, **inputs):
        branch = inputs.pop("branch", None)
        directory = self.repository()
        base = self.git(directory, "rev-parse", "HEAD").strip()

        if branch:
            self.git(directory, "checkout", "--quiet", "-b", branch)

        for message in messages:
            self.commit(directory, message)

        return self.check(directory, baseRef=base, **inputs)


if __name__ == "__main__":
    unittest.main()
