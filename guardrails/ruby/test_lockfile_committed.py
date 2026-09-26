#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

GEMFILE = fixture("lockfile-committed-Gemfile")

LOCK = fixture("Gemfile.lock")

GEMSPEC = fixture("lockfile-committed-widget.gemspec")


class LockfileCommittedTest(GuardrailTestCase):
    SCRIPT = "lockfile-committed.py"
    COLLECT = ["ruby"]

    def test_passes_a_project_that_commits_a_lock_file(self):
        directory = self.workspace(**{"Gemfile": GEMFILE, "Gemfile.lock": LOCK})

        result = self.check(directory)

        self.assert_passed(result)
        self.assertIn("locked by Gemfile.lock, written by Bundler 2.5.9", result.output)

    def test_fails_a_project_that_commits_none(self):
        directory = self.workspace(**{"Gemfile": GEMFILE})

        violation = self.assert_violation(self.check(directory), "commits no Gemfile.lock")

        self.assertEqual(violation["evidence"], "Gemfile")

    def test_skips_a_checkout_that_carries_a_gemspec_rather_than_a_gemfile(self):
        directory = self.workspace(**{"widget.gemspec": GEMSPEC})

        self.assert_skipped(self.check(directory), "no Gemfile in ., so Bundler has nothing to resolve or lock")

    def test_skips_a_directory_with_no_ruby_project(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Ruby project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"Gemfile": GEMFILE}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "api/Gemfile": GEMFILE,
            "api/Gemfile.lock": LOCK,
        })

        self.assert_passed(self.check(directory, projectDir="api"))


if __name__ == "__main__":
    unittest.main()
