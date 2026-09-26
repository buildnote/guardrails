#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MANAGED = fixture("dependencies-versioned-managed.csproj")

STANDALONE = fixture("standalone.csproj")

LIBRARY = fixture("library.csproj")

CENTRAL = fixture("dependencies-versioned-central.props")

GLOBAL = fixture("global.json")

SOLUTION = "Microsoft Visual Studio Solution File, Format Version 12.00\n"

WIDGET = "src/Widget/Widget.csproj"
LIB = "lib/Library.csproj"


class DependenciesVersionedTest(GuardrailTestCase):
    SCRIPT = "dependencies-versioned.py"
    COLLECT = ["dotnet"]

    def build(self, **files):
        return self.workspace(**dict({"global.json": GLOBAL, WIDGET: STANDALONE}, **files))

    def test_passes_a_build_where_a_central_version_supplies_them(self):
        directory = self.build(**{"Directory.Packages.props": CENTRAL, WIDGET: MANAGED})

        self.assert_passed(self.check(directory))

    def test_passes_a_build_where_every_reference_carries_its_own(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_reference_with_no_version_anywhere(self):
        directory = self.build(**{WIDGET: MANAGED})

        violation = self.assert_violation(self.check(directory), "references Serilog with no version of its own")

        self.assertEqual(violation["evidence"], "src/Widget/Widget.csproj (Serilog)")

    def test_fails_a_reference_the_central_props_does_not_name(self):
        directory = self.build(**{
            "Directory.Packages.props": CENTRAL,
            WIDGET: MANAGED,
            LIB: LIBRARY.replace(' Version="8.4.1"', ""),
        })

        violation = self.assert_violation(self.check(directory), "references Polly with no version of its own")

        self.assertEqual(violation["evidence"], "lib/Library.csproj (Polly)")

    def test_skips_a_central_props_that_could_not_be_read(self):
        directory = self.build(**{"Directory.Packages.props": "<Project>\n", WIDGET: MANAGED})

        self.assert_skipped(self.check(directory), "Directory.Packages.props could not be read")

    def test_skips_when_every_project_file_was_dropped(self):
        directory = self.build(**{"Widget.sln": SOLUTION})

        self.assert_skipped(self.check(directory, maxProjects="0"), "1 project files were left out")

    def test_checks_what_it_read_when_only_some_were_dropped(self):
        directory = self.build(**{LIB: LIBRARY, WIDGET: MANAGED})

        self.assert_passed(self.check(directory, maxProjects="1"))

    def test_skips_a_directory_with_no_dotnet_project(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no .NET project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{os.path.join("backend", WIDGET): STANDALONE})

        self.assert_passed(self.check(directory, projectDir="backend"))


if __name__ == "__main__":
    unittest.main()
