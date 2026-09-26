#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

DEPS = fixture("deps.edn")

PROJECT = fixture("project.clj")


class ClojureTest(CollectorTestCase):
    COLLECTOR = "clojure"

    def build(self, **files):
        return self.workspace(**dict({"deps.edn": DEPS}, **files))

    def test_reads_the_manifest_and_what_it_declares(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "deps.edn")
        self.assertEqual(facts["sources"], ["deps.edn"])
        self.assertEqual(facts["tool"], "clojure-cli")
        self.assertEqual(facts["paths"], ["src", "resources"])
        self.assertEqual(facts["aliases"], ["test"])
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "deps.edn", "name": None}])

    def test_reads_data_rather_than_by_pattern(self):
        self.assertEqual(self.collect(self.build())["scanned"], [])

    def test_reads_the_clojure_version_the_project_depends_on(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["declared"], {"version": "1.11.3", "source": "deps.edn", "pinned": True})

    def test_names_every_repository_beyond_the_defaults(self):
        facts = self.collect(self.build())

        self.assertEqual(
            facts["repositories"],
            [{"name": "clojars", "url": "https://repo.clojars.org/"}, {"name": "internal", "url": None}],
        )

    def test_names_the_alias_that_adds_a_dependency(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertEqual(by_name["lambdaisland/kaocha"]["scopes"], ["test"])
        self.assertEqual(by_name["ring/ring-core"]["scopes"], ["default"])
        self.assertEqual(by_name["ring/ring-core"]["source"], "deps.edn")

    def test_says_where_each_dependency_comes_from(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertEqual(by_name["ring/ring-core"]["origin"], "maven")
        self.assertEqual(by_name["io.github.company/queue"]["origin"], "git")
        self.assertEqual(by_name["company/local"]["origin"], "local")

    def test_reads_a_git_dependency_without_a_sha_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertTrue(by_name["io.github.company/queue"]["pinned"])
        self.assertFalse(by_name["io.github.company/drift"]["pinned"])
        self.assertFalse(by_name["company/local"]["pinned"])

    def test_reads_a_moving_version_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertFalse(by_name["cheshire/cheshire"]["pinned"])
        self.assertEqual(by_name["cheshire/cheshire"]["version"], "RELEASE")

    def test_reads_a_leiningen_project(self):
        facts = self.collect(self.workspace(**{"project.clj": PROJECT}))

        self.assertEqual(facts["tool"], "leiningen")
        self.assertEqual(facts["manifest"], "project.clj")
        self.assertEqual(facts["scanned"], ["project.clj"])
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "project.clj", "name": "company/widget"}])
        self.assertEqual(
            [(it["name"], it["version"]) for it in facts["dependencies"]["direct"]],
            [("org.clojure/clojure", "1.11.3"), ("ring/ring-core", "1.12.1")],
        )
        self.assertEqual(facts["declared"]["source"], "project.clj")

    def test_says_when_the_checkout_carries_both_tools(self):
        facts = self.collect(self.build(**{"project.clj": PROJECT}))

        self.assertEqual(facts["tool"], "both")
        self.assertEqual(facts["sources"], ["deps.edn", "project.clj"])
        self.assertEqual([it["manifest"] for it in facts["projects"]], ["deps.edn", "project.clj"])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.build())["dependencies"]["transitive"], [])

    def test_reports_a_manifest_that_could_not_be_read(self):
        facts = self.collect(self.workspace(**{"deps.edn": "{:deps {org.clojure/clojure {:mvn/version \"1.11.3\"}\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "deps.edn")
        self.assertEqual(facts["unparsed"][0]["reason"], "a collection is not closed")
        self.assertEqual(facts["dependencies"]["direct"], [])

    def test_reports_a_manifest_carrying_more_than_one_form(self):
        facts = self.collect(self.workspace(**{"deps.edn": "{:paths [\"src\"]}\n{:paths [\"other\"]}\n"}))

        self.assertEqual(facts["unparsed"][0]["reason"], "more than one form")

    def test_collects_nothing_where_there_is_no_clojure_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"service/deps.edn": DEPS})
        facts = self.collect(directory, projectDir="service")

        self.assertEqual(facts["directory"], "service")
        self.assertEqual(facts["declared"]["version"], "1.11.3")


if __name__ == "__main__":
    unittest.main()
