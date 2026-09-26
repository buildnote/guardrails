#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CURRENT = fixture("current.csproj")

BEHIND = CURRENT.replace("net8.0", "net6.0")

DESKTOP = CURRENT.replace("net8.0", "net6.0-windows")

LEGACY = fixture("legacy.csproj")

GLOBAL = fixture("global.json")

SOLUTION = "Microsoft Visual Studio Solution File, Format Version 12.00\n"

WIDGET = "src/Widget/Widget.csproj"
LEGACY_PROJECT = "src/Legacy/Legacy.csproj"


class TargetFrameworkFloorTest(GuardrailTestCase):
    SCRIPT = "target-framework-floor.py"
    COLLECT = ["dotnet"]

    def build(self, **files):
        return self.workspace(**dict({"global.json": GLOBAL, WIDGET: CURRENT}, **files))

    def test_passes_a_build_on_the_floor(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_project_behind_the_floor(self):
        directory = self.build(**{WIDGET: BEHIND})

        violation = self.assert_violation(self.check(directory), "targets net6.0, older than the net8.0 expected")

        self.assertEqual(violation["evidence"], "src/Widget/Widget.csproj")

    def test_compares_a_platform_specific_moniker(self):
        directory = self.build(**{WIDGET: DESKTOP})

        self.assert_violation(self.check(directory), "targets net6.0-windows, older than the net8.0 expected")

    def test_leaves_the_other_versioning_lines_alone(self):
        directory = self.build(**{LEGACY_PROJECT: LEGACY})

        self.assert_passed(self.check(directory))

    def test_names_every_project_declaring_the_moniker(self):
        directory = self.build(**{WIDGET: BEHIND, LEGACY_PROJECT: BEHIND})

        violation = self.assert_violation(self.check(directory), "targets net6.0")

        self.assertEqual(violation["evidence"], "src/Legacy/Legacy.csproj, src/Widget/Widget.csproj")

    def test_honours_the_floor_it_is_given(self):
        directory = self.build()

        self.assert_passed(self.check(directory, minFramework="net6.0"))
        self.assert_violation(self.check(directory, minFramework="net9.0"), "older than the net9.0 expected")

    def test_skips_a_floor_that_is_not_a_moniker(self):
        self.assert_skipped(self.check(self.build(), minFramework="netstandard2.0"), "is not a net<major>.<minor>")

    def test_skips_when_every_project_file_was_dropped(self):
        directory = self.build(**{"Widget.sln": SOLUTION})

        self.assert_skipped(self.check(directory, maxProjects="0"), "1 project files were left out")

    def test_checks_what_it_read_when_only_some_were_dropped(self):
        directory = self.build(**{LEGACY_PROJECT: BEHIND})

        violation = self.assert_violation(self.check(directory, maxProjects="1"), "targets net6.0")

        self.assertEqual(violation["evidence"], "src/Legacy/Legacy.csproj")

    def test_skips_a_directory_with_no_dotnet_project(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no .NET project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{os.path.join("backend", WIDGET): CURRENT})

        self.assert_passed(self.check(directory, projectDir="backend"))


if __name__ == "__main__":
    unittest.main()
