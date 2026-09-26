#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"


def workflow(*steps):
    rendered = "\n".join("      - %s" % step for step in steps)

    return "name: build\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n%s\n" % rendered


class ActionsPinnedByDigestTest(GuardrailTestCase):
    SCRIPT = "actions-pinned-by-digest.py"
    COLLECT = ["github"]

    def pipeline(self, text, **inputs):
        return self.check(self.workspace(**{".github/workflows/build.yml": text}), **inputs)

    def test_passes_an_action_pinned_to_a_sha(self):
        self.assert_passed(self.pipeline(workflow("uses: actions/checkout@%s" % SHA)))

    def test_fails_an_action_pinned_to_a_tag(self):
        self.assert_violation(
            self.pipeline(workflow("uses: actions/checkout@v4")),
            "pinned to v4 rather than to a commit sha",
        )

    def test_fails_an_action_pinned_to_a_branch(self):
        self.assert_violation(self.pipeline(workflow("uses: company/deploy@main")), "pinned to main")

    def test_ignores_a_local_action(self):
        self.assert_passed(self.pipeline(workflow("uses: ./.github/actions/setup")))

    def test_ignores_a_step_that_runs_a_command(self):
        self.assert_passed(self.pipeline(workflow("run: ./gradlew build")))

    def test_exempts_an_action_it_is_told_to_allow(self):
        self.assert_passed(self.pipeline(workflow("uses: actions/checkout@v4"), allow="actions/*"))

    def test_still_fails_an_action_no_glob_covers(self):
        self.assert_violation(
            self.pipeline(workflow("uses: company/deploy@v1"), allow="actions/*"),
            "pinned to v1",
        )

    def test_reports_every_unpinned_action(self):
        result = self.pipeline(workflow("uses: actions/checkout@v4", "uses: actions/setup-java@v4"))

        self.assertEqual(len(result.violations), 2)

    def test_names_the_workflow_it_found_it_in(self):
        result = self.pipeline(workflow("uses: actions/checkout@v4"))

        self.assertIn(".github/workflows/build.yml", result.violations[0]["evidence"])

    def test_skips_a_repository_with_no_pipeline(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "carries no GitHub Actions workflow")

    def test_skips_a_repository_that_carries_only_a_codeowners_file(self):
        self.assert_skipped(self.check(self.workspace(**{"CODEOWNERS": "* @company/platform\n"})), "carries no GitHub Actions workflow")


if __name__ == "__main__":
    unittest.main()
