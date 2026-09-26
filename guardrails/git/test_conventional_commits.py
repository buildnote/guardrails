#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


class ConventionalCommitsTest(GuardrailTestCase):
    SCRIPT = "conventional-commits.py"
    COLLECT = ["git"]

    def test_passes_messages_that_follow_the_specification(self):
        result = self.commits(
            "feat: add a widget",
            "fix(api): reject expired tokens",
            "feat(api)!: drop the v1 endpoint",
            "docs: explain the widget\n\nA body that starts after a blank line.\n\nNote: prose with a colon is not a footer.",
            "refactor(cli): rename the runner\n\nThe body.\n\nBREAKING CHANGE: the runner is now called differently.\nCo-authored-by: Someone <someone@buildnote.io>",
        )

        self.assert_passed(result)

    def test_fails_a_subject_that_is_not_conventional(self):
        self.assert_violation(self.commits("update stuff"), "does not follow Conventional Commits")

    def test_fails_a_subject_with_no_space_after_the_colon(self):
        self.assert_violation(self.commits("feat:add a widget"), "is missing the space after the colon")

    def test_fails_a_subject_with_an_empty_scope(self):
        self.assert_violation(self.commits("feat(): add a widget"), "declares an empty scope")

    def test_fails_a_body_that_does_not_start_after_a_blank_line(self):
        self.assert_violation(
            self.commits("feat: add a widget\nthe body starts too early"),
            "does not leave a blank line between the description and the body",
        )

    def test_fails_a_breaking_change_footer_that_is_not_uppercase(self):
        self.assert_violation(
            self.commits("feat: add a widget\n\nbreaking change: the widget replaces the gadget"),
            'writes the breaking change footer as "breaking change" rather than BREAKING CHANGE',
        )

    def test_fails_a_breaking_change_footer_with_no_description(self):
        self.assert_violation(
            self.commits("feat: add a widget\n\nBREAKING CHANGE:"),
            "has a BREAKING CHANGE footer with no description",
        )

    def test_reports_one_violation_per_commit(self):
        self.assert_violation(
            self.commits("feat(): add a widget\nthe body starts too early"),
            "declares an empty scope",
        )

    def test_evidence_names_the_commit_and_its_subject(self):
        violation = self.assert_violation(self.commits("update stuff"), "does not follow Conventional Commits")
        evidence = violation["evidence"]

        self.assertTrue(evidence.endswith(" update stuff"), evidence)
        self.assertEqual(len(evidence.split(" ")[0]), 7)

    def test_accepts_the_types_it_is_given(self):
        self.assert_passed(self.commits("wip: still going", types="wip|feat"))
        self.assert_violation(self.commits("feat: add a widget", types="wip"), "does not follow Conventional Commits")

    def test_passes_an_empty_range(self):
        self.assert_passed(self.commits())

    def test_skips_when_the_base_ref_cannot_be_resolved(self):
        directory = self.repository()
        self.commit(directory, "update stuff")

        self.assert_skipped(
            self.check(directory, baseRef="buildnote/not-a-real-ref"),
            "buildnote/not-a-real-ref is not resolvable",
        )

    def test_skips_outside_a_git_repository(self):
        self.assert_skipped(self.check(self.workspace()), "not a git repository")

    def commits(self, *messages, **inputs):
        directory = self.repository()
        base = self.git(directory, "rev-parse", "HEAD").strip()
        for message in messages:
            self.commit(directory, message)

        return self.check(directory, baseRef=base, **inputs)


if __name__ == "__main__":
    unittest.main()
