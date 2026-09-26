#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

PROJECT = fixture("project.csproj")

MULTI = fixture("multi.csproj")

CENTRAL = fixture("central.props")

GLOBAL = fixture("global.json")

WIDGET = "src/Widget/Widget.csproj"


class DotnetTest(CollectorTestCase):
    COLLECTOR = "dotnet"

    def solution(self, **files):
        return self.workspace(**dict({
            "global.json": GLOBAL,
            "Directory.Packages.props": CENTRAL,
            WIDGET: PROJECT,
            "src/Widget/packages.lock.json": "{\"version\": 1}\n",
        }, **files))

    def test_reads_the_projects_and_what_they_target(self):
        facts = self.collect(self.solution())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "src/Widget/Widget.csproj")
        self.assertEqual(facts["targetFrameworks"], ["net8.0"])
        self.assertEqual(
            facts["projects"],
            [{
                "path": "src/Widget",
                "manifest": "src/Widget/Widget.csproj",
                "name": "Company.Widget",
                "targetFrameworks": ["net8.0"],
            }],
        )

    def test_reads_the_sdk_global_json_pins(self):
        facts = self.collect(self.solution())

        self.assertEqual(facts["rollForward"], "disable")
        self.assertEqual(facts["declared"], {"version": "8.0.204", "source": "global.json", "pinned": True})

    def test_reads_a_roll_forward_policy_as_unpinned(self):
        facts = self.collect(self.solution(**{"global.json": "{\"sdk\": {\"version\": \"8.0.204\", \"rollForward\": \"latestFeature\"}}\n"}))

        self.assertFalse(facts["declared"]["pinned"])
        self.assertEqual(facts["rollForward"], "latestFeature")

    def test_takes_a_version_from_central_package_management(self):
        by_name = dict((it["name"], it) for it in self.collect(self.solution())["dependencies"]["direct"])

        self.assertEqual(by_name["Serilog"]["managedBy"], "Directory.Packages.props")
        self.assertEqual(by_name["Serilog"]["version"], "4.0.0")
        self.assertIsNone(by_name["Npgsql"]["managedBy"])
        self.assertTrue(self.collect(self.solution())["centralPackageManagement"])

    def test_reads_a_floating_version_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.solution())["dependencies"]["direct"])

        self.assertTrue(by_name["Npgsql"]["pinned"])
        self.assertFalse(by_name["Floating"]["pinned"])

    def test_reads_a_private_reference_as_a_development_one(self):
        by_name = dict((it["name"], it) for it in self.collect(self.solution())["dependencies"]["direct"])

        self.assertEqual(by_name["StyleCop.Analyzers"]["scopes"], ["development"])
        self.assertEqual(by_name["Npgsql"]["scopes"], ["default"])
        self.assertEqual(by_name["Npgsql"]["source"], "src/Widget/Widget.csproj")

    def test_reads_a_version_declared_as_a_child_element(self):
        directory = self.workspace(**{"lib/Lib.csproj": MULTI})
        facts = self.collect(directory)

        self.assertEqual(facts["dependencies"]["direct"][0]["version"], "2.1.0")
        self.assertEqual(facts["targetFrameworks"], ["net8.0", "netstandard2.0"])
        self.assertEqual(facts["projects"][0]["name"], "Lib")

    def test_names_the_solution_when_the_checkout_has_one(self):
        facts = self.collect(self.solution(**{"Widget.sln": "Microsoft Visual Studio Solution File\n"}))

        self.assertEqual(facts["solution"], "Widget.sln")
        self.assertEqual(facts["manifest"], "Widget.sln")

    def test_names_every_lock_file_committed(self):
        self.assertEqual(self.collect(self.solution())["lockfiles"], ["src/Widget/packages.lock.json"])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.solution())["dependencies"]["transitive"], [])

    def test_leaves_build_output_out(self):
        directory = self.solution(**{"src/Widget/obj/Stale.csproj": PROJECT})

        self.assertEqual([it["manifest"] for it in self.collect(directory)["projects"]], ["src/Widget/Widget.csproj"])

    def test_honours_the_project_ceiling_it_is_given(self):
        directory = self.solution(**{"lib/Lib.csproj": MULTI})

        facts = self.collect(directory, maxProjects="1")

        self.assertEqual(len(facts["projects"]), 1)
        self.assertEqual(facts["dropped"], 1)

    def test_drops_nothing_when_the_ceiling_is_not_reached(self):
        self.assertEqual(self.collect(self.solution())["dropped"], 0)

    def test_reports_a_project_file_that_could_not_be_read(self):
        facts = self.collect(self.workspace(**{"src/Bad.csproj": "<Project>\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "src/Bad.csproj")
        self.assertEqual(facts["projects"][0]["name"], None)

    def test_reports_a_global_json_that_could_not_be_read(self):
        facts = self.collect(self.solution(**{"global.json": "{ not json\n"}))

        self.assertIn({"path": "global.json"}, [{"path": it["path"]} for it in facts["unparsed"]])
        self.assertIsNone(facts["declared"])

    def test_collects_nothing_where_there_is_no_dotnet_project(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"backend/src/Widget/Widget.csproj": PROJECT})
        facts = self.collect(directory, projectDir="backend")

        self.assertEqual(facts["directory"], "backend")
        self.assertEqual(facts["projects"][0]["manifest"], "backend/src/Widget/Widget.csproj")


if __name__ == "__main__":
    unittest.main()
