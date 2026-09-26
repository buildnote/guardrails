#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

MANAGED = fixture("central-package-management-managed.csproj")

STANDALONE = fixture("standalone.csproj")

CENTRAL = fixture("central-package-management-central.props")

TURNED_OFF = CENTRAL.replace("<ManagePackageVersionsCentrally>true", "<ManagePackageVersionsCentrally>false")

GLOBAL = fixture("global.json")

WIDGET = "src/Widget/Widget.csproj"


class CentralPackageManagementTest(GuardrailTestCase):
    SCRIPT = "central-package-management.py"
    COLLECT = ["dotnet"]

    def build(self, **files):
        return self.workspace(**dict({"global.json": GLOBAL, WIDGET: STANDALONE}, **files))

    def test_passes_a_build_that_manages_versions_centrally(self):
        directory = self.build(**{"Directory.Packages.props": CENTRAL, WIDGET: MANAGED})

        self.assert_passed(self.check(directory))

    def test_fails_a_build_where_every_project_decides_its_own(self):
        violation = self.assert_violation(self.check(self.build()), "decide its own package versions")

        self.assertEqual(violation["evidence"], "src/Widget/Widget.csproj")

    def test_fails_a_build_that_turned_central_management_off(self):
        directory = self.build(**{"Directory.Packages.props": TURNED_OFF})

        self.assert_violation(self.check(directory), "decide its own package versions")

    def test_skips_a_central_props_that_could_not_be_read(self):
        directory = self.build(**{"Directory.Packages.props": "<Project>\n"})

        self.assert_skipped(self.check(directory), "Directory.Packages.props could not be read")

    def test_skips_a_directory_with_no_dotnet_project(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no .NET project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "backend/Directory.Packages.props": CENTRAL,
            os.path.join("backend", WIDGET): MANAGED,
        })

        self.assert_passed(self.check(directory, projectDir="backend"))


if __name__ == "__main__":
    unittest.main()
