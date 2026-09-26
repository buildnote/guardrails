#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MIX = fixture("no-git-dependencies-mix.exs")

UMBRELLA = fixture("umbrella.exs")

CORE = fixture("core.exs")


class NoGitDependenciesTest(GuardrailTestCase):
    SCRIPT = "no-git-dependencies.py"
    COLLECT = ["elixir"]

    def test_passes_a_project_with_no_git_dependencies(self):
        self.assert_passed(self.check(self.workspace(**{"mix.exs": MIX, "mix.lock": "%{}\n"})))

    def test_fails_a_dependency_taken_from_github(self):
        source = MIX.replace('{:queue, path: "../queue"}', '{:widget_ui, github: "company/widget_ui"}')
        directory = self.workspace(**{"mix.exs": source})

        violation = self.assert_violation(self.check(directory), "mix.exs takes widget_ui from a git repository")

        self.assertEqual(violation["evidence"], "widget_ui (mix.exs)")

    def test_fails_a_dependency_taken_from_a_git_url(self):
        source = MIX.replace(
            '{:queue, path: "../queue"}',
            '{:queue, git: "https://github.com/company/queue.git", tag: "v1.4.0"}',
        )
        directory = self.workspace(**{"mix.exs": source})

        self.assert_violation(self.check(directory), "mix.exs takes queue from a git repository")

    def test_names_every_dependency_taken_from_git(self):
        source = MIX.replace(
            '{:queue, path: "../queue"}',
            '{:queue, github: "company/queue"},\n      {:widget_ui, github: "company/widget_ui"}',
        )
        result = self.check(self.workspace(**{"mix.exs": source}))

        self.assertEqual([it["evidence"] for it in result.violations], ["queue (mix.exs)", "widget_ui (mix.exs)"])
        self.assertEqual(result.code, 1)

    def test_names_the_umbrella_application_declaring_it(self):
        directory = self.workspace(**{
            "mix.exs": UMBRELLA,
            "apps/core/mix.exs": CORE,
        })

        violation = self.assert_violation(self.check(directory), "apps/core/mix.exs takes widget_ui")

        self.assertEqual(violation["evidence"], "widget_ui (apps/core/mix.exs)")

    def test_skips_a_directory_with_no_mix_project(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": "module company\n"})), "no Mix project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"mix.exs": MIX})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"server/mix.exs": MIX})

        self.assert_passed(self.check(directory, projectDir="server"))


if __name__ == "__main__":
    unittest.main()
