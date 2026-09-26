#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

POM = fixture("pom.xml")

MODULE_POM = fixture("module-pom.xml")


class MavenCollectorTest(CollectorTestCase):
    COLLECTOR = "maven"

    def test_collects_the_root_pom(self):
        facts = self.collect(self.workspace(**{"pom.xml": POM}))

        self.assertEqual(facts["pom"], "pom.xml")
        self.assertEqual(facts["sources"], ["pom.xml"])
        self.assertFalse(facts["malformed"])
        self.assertEqual(facts["coordinates"], {
            "groupId": "io.buildnote",
            "artifactId": "widget",
            "version": "1.2.3",
            "packaging": "pom",
        })

    def test_collects_the_properties(self):
        facts = self.collect(self.workspace(**{"pom.xml": POM}))

        self.assertEqual(facts["properties"]["maven.compiler.release"], "21")

    def test_collects_the_modules(self):
        directory = self.workspace(**{"pom.xml": POM, "service/pom.xml": MODULE_POM})

        modules = self.collect(directory)["modules"]

        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["path"], "service")
        self.assertEqual(modules[0]["pom"], "service/pom.xml")
        self.assertEqual(modules[0]["coordinates"]["artifactId"], "service")
        self.assertEqual(modules[0]["coordinates"]["groupId"], "io.buildnote")

    def test_reports_a_module_that_is_not_checked_in(self):
        modules = self.collect(self.workspace(**{"pom.xml": POM}))["modules"]

        self.assertIsNone(modules[0]["pom"])
        self.assertIsNone(modules[0]["coordinates"])

    def test_collects_the_declared_dependencies(self):
        dependencies = self.collect(self.workspace(**{"pom.xml": POM}))["dependencies"]

        self.assertEqual(dependencies["transitive"], [])
        self.assertEqual(
            [(it["path"], it["version"], it["scopes"]) for it in dependencies["direct"]],
            [
                ("org.junit:junit-bom", "6.0.3", ["import"]),
                ("org.slf4j:slf4j-api", "1.7.36", ["compile"]),
                ("junit:junit", "4.13.2", ["test"]),
                ("org.unpinned:widget", None, ["compile"]),
                ("org.graalvm.sdk:graal-sdk", "23.1.2", ["compile"]),
            ],
        )
        self.assertEqual(dependencies["direct"][0]["source"], "pom.xml")
        self.assertNotIn("profile", dependencies["direct"][0])
        self.assertTrue(dependencies["direct"][0]["platform"])
        self.assertNotIn("platform", dependencies["direct"][1])

    def test_collects_the_dependencies_a_profile_declares(self):
        direct = self.collect(self.workspace(**{"pom.xml": POM}))["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"], it["profile"]) for it in direct if it.get("profile")],
            [("org.graalvm.sdk:graal-sdk", "23.1.2", "native")],
        )

    def test_collects_the_dependencies_a_module_declares(self):
        directory = self.workspace(**{"pom.xml": POM, "service/pom.xml": MODULE_POM})

        direct = [it for it in self.collect(directory)["dependencies"]["direct"] if it["source"] != "pom.xml"]

        self.assertEqual(
            [(it["path"], it["version"]) for it in direct],
            [
                ("com.google.guava:guava", "33.0.0-jre"),
                ("com.company:widget-core", "1.2.3"),
                ("org.junit.jupiter:junit-jupiter-api", "6.0.3"),
            ],
        )
        self.assertEqual(direct[0]["source"], "service/pom.xml")
        self.assertNotIn("managedBy", direct[0])

    def test_takes_the_version_an_imported_bom_supplies(self):
        directory = self.workspace(**{"pom.xml": POM, "service/pom.xml": MODULE_POM})

        direct = self.collect(directory)["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"], it["managedBy"]) for it in direct if it.get("managedBy")],
            [("org.junit.jupiter:junit-jupiter-api", "6.0.3", "org.junit:junit-bom:6.0.3")],
        )

    def module_under_a_parent(self, pom=MODULE_POM):
        root = self.workspace(**{"pom.xml": POM, "service/pom.xml": pom})

        return root, os.path.join(root, "service")

    def test_reads_the_parent_pom_from_above_the_module(self):
        root, module = self.module_under_a_parent()
        self.rooted_at(root)

        facts = self.collect(module)

        self.assertEqual(facts["directory"], "service")
        self.assertEqual(facts["root"], ".")
        self.assertEqual(facts["pom"], "service/pom.xml")
        self.assertEqual(facts["sources"], ["service/pom.xml", "pom.xml"])
        self.assertEqual(facts["properties"]["maven.compiler.release"], "21")
        self.assertEqual(facts["coordinates"]["artifactId"], "service")
        self.assertEqual(facts["modules"], [])

    def test_states_every_path_from_the_directory_the_cli_runs_in(self):
        root, module = self.module_under_a_parent()
        self.rooted_at(root)

        self.assertNotIn("..", json.dumps(self.collect(module)))

    def test_takes_the_versions_the_parent_manages_and_imports(self):
        root, module = self.module_under_a_parent()
        self.rooted_at(root)

        direct = self.collect(module)["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"], it.get("managedBy")) for it in direct],
            [
                ("com.google.guava:guava", "33.0.0-jre", None),
                ("com.company:widget-core", "1.2.3", None),
                ("org.junit.jupiter:junit-jupiter-api", "6.0.3", "org.junit:junit-bom:6.0.3"),
            ],
        )

    def test_leaves_the_parent_alone_when_it_is_resolved_from_the_repository(self):
        root, module = self.module_under_a_parent(
            MODULE_POM.replace("  </parent>", "    <relativePath/>\n  </parent>", 1)
        )
        self.rooted_at(root)

        facts = self.collect(module)

        self.assertIsNone(facts["root"])
        self.assertEqual(facts["sources"], ["service/pom.xml"])
        self.assertIsNone(facts["dependencies"]["direct"][0]["version"])

    def test_never_reads_above_the_directory_the_cli_runs_in(self):
        _, module = self.module_under_a_parent()
        self.rooted_at(module)

        facts = self.collect(module)

        self.assertIsNone(facts["root"])
        self.assertIsNone(facts["dependencies"]["direct"][0]["version"])

    def test_reports_a_malformed_pom(self):
        facts = self.collect(self.workspace(**{"pom.xml": "<project>\n"}))

        self.assertTrue(facts["malformed"])
        self.assertIsNone(facts["coordinates"])

    def test_collects_nothing_for_a_project_that_is_not_a_maven_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"build.gradle.kts": "plugins { }\n"})))

    def test_reports_a_directory_that_does_not_exist(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["sources"], [])


if __name__ == "__main__":
    unittest.main()
