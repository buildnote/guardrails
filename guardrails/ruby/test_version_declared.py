#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

GEMFILE = fixture("versioned.Gemfile")

WITHOUT_VERSION = fixture("without-version.Gemfile")


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["ruby"]

    def test_passes_a_project_that_declares_the_ruby_directive(self):
        self.assert_passed(self.check(self.workspace(**{"Gemfile": GEMFILE})))

    def test_passes_a_project_that_declares_a_ruby_version_file(self):
        directory = self.workspace(**{"Gemfile": WITHOUT_VERSION, ".ruby-version": "3.2.4\n"})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_declares_none(self):
        directory = self.workspace(**{"Gemfile": WITHOUT_VERSION})

        violation = self.assert_violation(self.check(directory), "No Ruby version declared in Gemfile")

        self.assertEqual(violation["evidence"], "Gemfile")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"Gemfile": GEMFILE.replace("3.3.1", "2.7.8")})

        violation = self.assert_violation(self.check(directory), "asks for Ruby 2.7.8, older than the 3.0 expected")

        self.assertEqual(violation["evidence"], "Gemfile (Ruby 2.7.8)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"Gemfile": GEMFILE})

        self.assert_passed(self.check(directory, minVersion="3.3"))
        self.assert_violation(self.check(directory, minVersion="3.4"), "older than the 3.4 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"Gemfile": WITHOUT_VERSION, ".ruby-version": "3.3\n"})

        self.assert_passed(self.check(directory, minVersion="3.3.0"))
        self.assert_violation(self.check(directory, minVersion="3.3.1"), "older than the 3.3.1 expected")

    def test_reads_a_constraint_rather_than_an_exact_version(self):
        directory = self.workspace(**{"Gemfile": GEMFILE.replace('ruby "3.3.1"', 'ruby ">= 3.2"')})

        self.assert_passed(self.check(directory))
        self.assert_violation(self.check(directory, minVersion="3.3"), "asks for Ruby >= 3.2")

    def test_skips_a_directory_with_no_ruby_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.kt": "fun main() {}\n"})), "no Ruby project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"Gemfile": GEMFILE}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/Gemfile": GEMFILE})

        self.assert_passed(self.check(directory, projectDir="api"))


if __name__ == "__main__":
    unittest.main()
