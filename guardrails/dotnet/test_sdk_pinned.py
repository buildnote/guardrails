#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

PROJECT = fixture("dependencies-versioned-managed.csproj")

CENTRAL = fixture("central-package-management-central.props")

PINNED = fixture("global.json")

ROLLING = fixture("rolling.json")

WIDGET = "src/Widget/Widget.csproj"


class SdkPinnedTest(GuardrailTestCase):
    SCRIPT = "sdk-pinned.py"
    COLLECT = ["dotnet"]

    def build(self, **files):
        return self.workspace(**dict({"Directory.Packages.props": CENTRAL, WIDGET: PROJECT}, **files))

    def test_passes_a_build_that_pins_the_sdk(self):
        self.assert_passed(self.check(self.build(**{"global.json": PINNED})))

    def test_fails_a_build_that_pins_none(self):
        violation = self.assert_violation(self.check(self.build()), "pins no SDK version")

        self.assertEqual(violation["evidence"], "src/Widget/Widget.csproj")

    def test_fails_a_global_json_that_rolls_forward(self):
        directory = self.build(**{"global.json": ROLLING})

        violation = self.assert_violation(self.check(directory), "rolls forward with latestFeature")

        self.assertEqual(violation["evidence"], "global.json (SDK 8.0.204)")

    def test_names_a_global_json_that_declares_no_version(self):
        directory = self.build(**{"global.json": '{"sdk": {"rollForward": "latestMinor"}}\n'})

        violation = self.assert_violation(self.check(directory), "pins no SDK version")

        self.assertEqual(violation["evidence"], "global.json")

    def test_skips_a_global_json_that_could_not_be_read(self):
        directory = self.build(**{"global.json": "{ not json\n"})

        self.assert_skipped(self.check(directory), "global.json could not be read")

    def test_skips_a_directory_with_no_dotnet_project(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no .NET project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(**{"global.json": PINNED}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "backend/global.json": PINNED,
            os.path.join("backend", WIDGET): PROJECT,
        })

        self.assert_passed(self.check(directory, projectDir="backend"))


if __name__ == "__main__":
    unittest.main()
