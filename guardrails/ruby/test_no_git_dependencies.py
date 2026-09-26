#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

GEMFILE = fixture("no-git-dependencies-Gemfile")

FROM_GITHUB = fixture("from-github.Gemfile")

GEMSPEC = fixture("no-git-dependencies-widget.gemspec")

FROM_GIT = fixture("from-git.Gemfile")


class NoGitDependenciesTest(GuardrailTestCase):
    SCRIPT = "no-git-dependencies.py"
    COLLECT = ["ruby"]

    def test_passes_a_project_whose_gems_come_from_the_gem_source(self):
        self.assert_passed(self.check(self.workspace(**{"Gemfile": GEMFILE})))

    def test_says_what_was_read_by_pattern_when_it_finds_none(self):
        result = self.check(self.workspace(**{"Gemfile": GEMFILE, "widget.gemspec": GEMSPEC}))

        self.assert_passed(result)
        self.assertIn("no gem is fetched from git in Gemfile, widget.gemspec", result.output)
        self.assertIn("a gem added inside a condition, a loop or an eval is not seen", result.output)

    def test_fails_a_gem_fetched_from_github(self):
        directory = self.workspace(**{"Gemfile": FROM_GITHUB})

        violation = self.assert_violation(
            self.check(directory), "Gemfile declares company-widget from a git repository rather than from a gem source"
        )

        self.assertEqual(violation["evidence"], "Gemfile (company-widget)")

    def test_fails_every_git_gem_it_can_see(self):
        result = self.check(self.workspace(**{"Gemfile": FROM_GIT}))

        self.assertEqual([it["evidence"] for it in result.violations], ["Gemfile (company-widget)", "Gemfile (company-queue)"])
        self.assertEqual(result.code, 1)

    def test_skips_a_directory_with_no_ruby_project(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": "module company\n"})), "no Ruby project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"Gemfile": GEMFILE}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/Gemfile": FROM_GITHUB})

        self.assert_violation(self.check(directory, projectDir="api"), "from a git repository")


if __name__ == "__main__":
    unittest.main()
