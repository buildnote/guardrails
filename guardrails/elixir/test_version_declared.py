#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MIX = fixture("version-declared-mix.exs")

WITHOUT_VERSION = MIX.replace('      elixir: "~> 1.16",\n', "")


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["elixir"]

    def test_passes_a_project_that_declares_an_elixir_version(self):
        self.assert_passed(self.check(self.workspace(**{"mix.exs": MIX})))

    def test_fails_a_project_that_declares_none(self):
        directory = self.workspace(**{"mix.exs": WITHOUT_VERSION})

        violation = self.assert_violation(self.check(directory), "No Elixir version declared in mix.exs")

        self.assertEqual(violation["evidence"], "mix.exs")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"mix.exs": MIX.replace("~> 1.16", "~> 1.12")})

        violation = self.assert_violation(self.check(directory), "asks for Elixir ~> 1.12, older than the 1.14")

        self.assertEqual(violation["evidence"], "mix.exs (Elixir ~> 1.12)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"mix.exs": MIX})

        self.assert_passed(self.check(directory, minVersion="1.16"))
        self.assert_violation(self.check(directory, minVersion="1.17"), "older than the 1.17 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"mix.exs": MIX.replace('"~> 1.16"', '"1.16"')})

        self.assert_passed(self.check(directory, minVersion="1.16.0"))
        self.assert_violation(self.check(directory, minVersion="1.16.1"), "older than the 1.16.1 expected")

    def test_skips_a_directory_with_no_mix_project(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Mix project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"mix.exs": MIX}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"server/mix.exs": MIX})

        self.assert_passed(self.check(directory, projectDir="server"))


if __name__ == "__main__":
    unittest.main()
