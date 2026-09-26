#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

MIX = fixture("mix.exs")
UMBRELLA = fixture("umbrella.exs")
APP = fixture("app.exs")


class ElixirTest(CollectorTestCase):
    COLLECTOR = "elixir"

    def project(self, **files):
        return self.workspace(**dict({"mix.exs": MIX, "mix.lock": "%{}\n"}, **files))

    def test_reads_the_application_the_project_declares(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "mix.exs")
        self.assertEqual(facts["sources"], ["mix.exs"])
        self.assertEqual(facts["app"], "widget")
        self.assertEqual(facts["version"], "1.2.3")
        self.assertFalse(facts["umbrella"])
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "mix.exs", "name": "widget"}])

    def test_says_the_manifest_is_read_by_pattern(self):
        self.assertEqual(self.collect(self.project())["scanned"], ["mix.exs"])

    def test_reads_the_elixir_version_the_project_asks_for(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["declared"], {"version": "~> 1.16", "source": "mix.exs", "pinned": False})

    def test_reads_an_exact_constraint_as_pinned(self):
        facts = self.collect(self.project(**{"mix.exs": MIX.replace('elixir: "~> 1.16"', 'elixir: "1.16.2"')}))

        self.assertTrue(facts["declared"]["pinned"])

    def test_names_the_environments_a_dependency_is_only_compiled_in(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["credo"]["scopes"], ["dev", "test"])
        self.assertEqual(by_name["dialyxir"]["scopes"], ["dev"])
        self.assertEqual(by_name["phoenix"]["scopes"], ["default"])

    def test_reads_a_pessimistic_requirement_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertTrue(by_name["jason"]["pinned"])
        self.assertFalse(by_name["phoenix"]["pinned"])
        self.assertEqual(by_name["phoenix"]["version"], "~> 1.7.11")
        self.assertEqual(by_name["phoenix"]["source"], "mix.exs")

    def test_says_where_each_dependency_comes_from(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["phoenix"]["origin"], "hex")
        self.assertEqual(by_name["queue"]["origin"], "path")
        self.assertEqual(by_name["widget_ui"]["origin"], "git")
        self.assertIsNone(by_name["queue"]["version"])

    def test_leaves_a_commented_out_dependency_out(self):
        names = [it["name"] for it in self.collect(self.project())["dependencies"]["direct"]]

        self.assertNotIn("commented", names)

    def test_reads_every_application_of_an_umbrella(self):
        directory = self.workspace(**{
            "mix.exs": UMBRELLA,
            "apps/core/mix.exs": APP,
        })
        facts = self.collect(directory)

        self.assertTrue(facts["umbrella"])
        self.assertEqual(facts["sources"], ["mix.exs", "apps/core/mix.exs"])
        self.assertEqual(
            [(it["path"], it["name"]) for it in facts["projects"]], [(".", None), ("apps/core", "core")]
        )
        self.assertEqual(
            [(it["name"], it["source"]) for it in facts["dependencies"]["direct"]],
            [("telemetry", "apps/core/mix.exs")],
        )

    def test_names_the_lock_file_when_one_is_committed(self):
        self.assertEqual(self.collect(self.project())["lockfiles"], ["mix.lock"])
        self.assertEqual(self.collect(self.workspace(**{"mix.exs": MIX}))["lockfiles"], [])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.project())["dependencies"]["transitive"], [])

    def test_reports_an_umbrella_application_that_could_not_be_read(self):
        directory = self.workspace(**{"mix.exs": UMBRELLA})
        os.makedirs(os.path.join(directory, "apps", "core", "mix.exs"))
        facts = self.collect(directory)

        self.assertEqual(
            facts["unparsed"], [{"path": "apps/core/mix.exs", "reason": "the manifest could not be read"}]
        )
        self.assertEqual([(it["path"], it["name"]) for it in facts["projects"]], [(".", None), ("apps/core", None)])

    def test_reports_a_manifest_that_is_a_directory(self):
        directory = self.workspace()
        os.mkdir(os.path.join(directory, "mix.exs"))

        self.assertIsNone(self.collect(directory))

    def test_collects_nothing_where_there_is_no_mix_project(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"server/mix.exs": MIX})
        facts = self.collect(directory, projectDir="server")

        self.assertEqual(facts["directory"], "server")
        self.assertEqual(facts["app"], "widget")


if __name__ == "__main__":
    unittest.main()
