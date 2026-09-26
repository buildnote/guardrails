#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("build.sbt")

PROPERTIES = "project/build.properties"
PLUGINS = "project/plugins.sbt"


class ScalaTest(CollectorTestCase):
    COLLECTOR = "scala"

    def build(self, **files):
        return self.workspace(**dict({
            "build.sbt": BUILD,
            PROPERTIES: "sbt.version=1.9.9\n",
        }, **files))

    def test_reads_the_build_and_the_versions_it_pins(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "build.sbt")
        self.assertEqual(facts["sources"], ["build.sbt", "project/build.properties"])
        self.assertEqual(facts["sbt"], "1.9.9")
        self.assertEqual(facts["declared"], {"version": "3.4.1", "source": "build.sbt", "pinned": True})

    def test_says_the_build_file_is_read_by_pattern(self):
        self.assertEqual(self.collect(self.build())["scanned"], ["build.sbt"])

    def test_names_every_subproject_the_reader_saw(self):
        facts = self.collect(self.build())

        self.assertEqual(
            [(it["path"], it["name"], it["manifest"]) for it in facts["projects"]],
            [(".", None, "build.sbt"), ("core", "core", "build.sbt"), ("server", "server", "build.sbt")],
        )

    def test_reads_coordinates_without_the_binary_version_sbt_appends(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertTrue(by_name["org.typelevel:cats-effect"]["crossVersion"])
        self.assertFalse(by_name["org.postgresql:postgresql"]["crossVersion"])
        self.assertEqual(by_name["org.typelevel:cats-effect"]["version"], "3.5.4")
        self.assertEqual(by_name["org.typelevel:cats-effect"]["source"], "build.sbt")

    def test_names_the_configuration_an_entry_is_scoped_to(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertEqual(by_name["org.scalameta:munit"]["scopes"], ["Test"])
        self.assertEqual(by_name["org.slf4j:slf4j-api"]["scopes"], ["provided"])
        self.assertEqual(by_name["org.typelevel:cats-effect"]["scopes"], ["default"])

    def test_reads_an_unresolved_revision_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertIsNone(by_name["com.company:queue"]["version"])
        self.assertFalse(by_name["com.company:queue"]["pinned"])
        self.assertTrue(by_name["org.postgresql:postgresql"]["pinned"])

    def test_leaves_a_commented_out_dependency_out(self):
        names = [it["name"] for it in self.collect(self.build())["dependencies"]["direct"]]

        self.assertNotIn("com.evil:commented", names)

    def test_names_the_plugins_the_build_itself_runs(self):
        facts = self.collect(self.build(**{PLUGINS: 'addSbtPlugin("org.scalameta" % "sbt-scalafmt" % "2.5.2")\n'}))

        self.assertEqual(facts["plugins"], ["org.scalameta:sbt-scalafmt"])
        self.assertIn("project/plugins.sbt", facts["scanned"])
        self.assertIn("project/plugins.sbt", facts["sources"])

    def test_names_a_lock_file_when_a_plugin_wrote_one(self):
        self.assertEqual(self.collect(self.build())["lockfiles"], [])
        self.assertEqual(self.collect(self.build(**{"build.sbt.lock": "{}\n"}))["lockfiles"], ["build.sbt.lock"])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.build())["dependencies"]["transitive"], [])

    def test_reports_a_build_file_that_could_not_be_read(self):
        directory = self.workspace(**{PROPERTIES: "sbt.version=1.9.9\n"})
        os.mkdir(os.path.join(directory, "build.sbt"))
        facts = self.collect(directory)

        self.assertEqual(
            facts["unparsed"], [{"path": "build.sbt", "reason": "the build file could not be read"}]
        )
        self.assertIsNone(facts["declared"])

    def test_collects_nothing_where_there_is_no_sbt_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/build.sbt": BUILD})
        facts = self.collect(directory, projectDir="engine")

        self.assertEqual(facts["directory"], "engine")
        self.assertEqual(facts["declared"]["version"], "3.4.1")


if __name__ == "__main__":
    unittest.main()
