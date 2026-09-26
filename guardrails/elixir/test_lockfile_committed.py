#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MIX = fixture("lockfile-committed-mix.exs")

LOCK = fixture("mix.lock")


class LockfileCommittedTest(GuardrailTestCase):
    SCRIPT = "lockfile-committed.py"
    COLLECT = ["elixir"]

    def test_passes_a_project_that_commits_a_lock_file(self):
        directory = self.workspace(**{"mix.exs": MIX, "mix.lock": LOCK})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_commits_none(self):
        directory = self.workspace(**{"mix.exs": MIX})

        violation = self.assert_violation(self.check(directory), "commits no mix.lock")

        self.assertEqual(violation["evidence"], "mix.exs")

    def test_skips_a_directory_with_no_mix_project(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": "module company\n"})), "no Mix project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"mix.exs": MIX, "mix.lock": LOCK})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "server/mix.exs": MIX,
            "server/mix.lock": LOCK,
        })

        self.assert_passed(self.check(directory, projectDir="server"))


if __name__ == "__main__":
    unittest.main()
