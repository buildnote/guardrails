#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

GEMFILE = fixture("lockfile-committed-Gemfile")

TWO_SOURCES = fixture("two-sources.Gemfile")

INTERNAL_ONLY = fixture("internal-only.Gemfile")

GEMSPEC = fixture("no-git-dependencies-widget.gemspec")


class SingleGemSourceTest(GuardrailTestCase):
    SCRIPT = "single-gem-source.py"
    COLLECT = ["ruby"]

    def test_passes_a_project_that_resolves_from_one_trusted_source(self):
        result = self.check(self.workspace(**{"Gemfile": GEMFILE}))

        self.assert_passed(result)
        self.assertIn("gems resolve from https://rubygems.org", result.output)
        self.assertIn("Gemfile is Ruby read by pattern", result.output)
        self.assertIn("a source named inside a condition, a loop or an eval is not seen", result.output)

    def test_reads_a_trailing_slash_as_the_same_source(self):
        directory = self.workspace(**{"Gemfile": GEMFILE.replace("rubygems.org", "rubygems.org/")})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_names_a_second_source(self):
        directory = self.workspace(**{"Gemfile": TWO_SOURCES})
        trusted = "https://rubygems.org,https://gems.internal.example.com"

        violation = self.assert_violation(
            self.check(directory, allowedSources=trusted), "resolves gems from 2 sources"
        )

        self.assertEqual(violation["evidence"], "Gemfile")
        self.assertIn("dependency confusion", violation["message"])

    def test_fails_a_source_the_repository_does_not_trust(self):
        directory = self.workspace(**{"Gemfile": INTERNAL_ONLY})

        violation = self.assert_violation(
            self.check(directory), "which is not one of the sources this repository trusts"
        )

        self.assertEqual(violation["evidence"], "Gemfile (https://gems.internal.example.com)")

    def test_reports_the_second_source_and_the_untrusted_one(self):
        result = self.check(self.workspace(**{"Gemfile": TWO_SOURCES}))

        self.assertEqual(len(result.violations), 2)
        self.assertEqual(result.code, 1)

    def test_honours_the_sources_it_is_given(self):
        directory = self.workspace(**{"Gemfile": INTERNAL_ONLY})

        self.assert_passed(self.check(directory, allowedSources="https://gems.internal.example.com"))

    def test_falls_back_to_the_trusted_sources_when_it_is_given_nothing(self):
        directory = self.workspace(**{"Gemfile": INTERNAL_ONLY})

        self.assert_violation(self.check(directory, allowedSources=""), "https://rubygems.org")

    def test_checks_the_number_of_sources_when_none_is_named_as_trusted(self):
        result = self.check(self.workspace(**{"Gemfile": INTERNAL_ONLY}), allowedSources=",")

        self.assert_passed(result)
        self.assertIn("no gem source is named as trusted", result.output)

        self.assert_violation(
            self.check(self.workspace(**{"Gemfile": TWO_SOURCES}), allowedSources=","), "resolves gems from 2 sources"
        )

    def test_skips_a_checkout_that_names_no_gem_source(self):
        directory = self.workspace(**{"widget.gemspec": GEMSPEC})

        self.assert_skipped(self.check(directory), "widget.gemspec names no gem source")

    def test_skips_a_directory_with_no_ruby_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Ruby project in .")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/Gemfile": GEMFILE})

        self.assert_passed(self.check(directory, projectDir="api"))


if __name__ == "__main__":
    unittest.main()
