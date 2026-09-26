#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, collector_script

VERSION_CATALOG = "gradle/libs.versions.toml"


class KotlinCollectorTest(CollectorTestCase):
    COLLECTOR = "kotlin"

    def test_collects_the_version_the_gradle_manifest_declares(self):
        directory = self.workspace(**{
            "settings.gradle.kts": 'rootProject.name = "widget"\n',
            "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
        })

        facts = self.collect(directory)

        self.assertTrue(facts["exists"])
        self.assertEqual(facts["sources"], ["build.gradle.kts"])
        self.assertEqual(facts["declared"], {"version": "2.0.0", "source": "build.gradle.kts"})

    def test_collects_the_version_the_groovy_manifest_declares(self):
        directory = self.workspace(**{
            "build.gradle": "plugins { id 'org.jetbrains.kotlin.jvm' version '1.9.24' }\n"
        })

        self.assertEqual(self.collect(directory)["declared"], {"version": "1.9.24", "source": "build.gradle"})

    def test_collects_the_version_the_catalog_declares(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            VERSION_CATALOG: '[versions]\nkotlin = "2.0.20"\njunit = "5.11.0"\n',
        })

        self.assertEqual(self.collect(directory)["declared"], {"version": "2.0.20", "source": VERSION_CATALOG})

    def test_takes_the_version_the_root_of_the_build_declares(self):
        root = self.workspace(**{
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
            "service/build.gradle.kts": "plugins { }\n",
        })
        self.rooted_at(root)

        facts = self.collect(os.path.join(root, "service"))

        self.assertEqual(facts["declared"], {"version": "2.0.0", "source": "build.gradle.kts"})

    def test_takes_the_catalog_of_the_root_of_the_build(self):
        root = self.workspace(**{
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": "plugins { }\n",
            VERSION_CATALOG: '[versions]\nkotlin = "2.0.20"\n',
            "service/build.gradle.kts": "plugins { }\n",
        })
        self.rooted_at(root)

        facts = self.collect(os.path.join(root, "service"))

        self.assertEqual(facts["declared"], {"version": "2.0.20", "source": VERSION_CATALOG})

    def test_prefers_the_manifest_over_the_catalog(self):
        directory = self.workspace(**{
            "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
            VERSION_CATALOG: '[versions]\nkotlin = "2.0.20"\n',
        })

        self.assertEqual(self.collect(directory)["declared"], {"version": "2.0.0", "source": "build.gradle.kts"})

    def test_collects_the_version_the_pom_declares(self):
        directory = self.workspace(**{
            "pom.xml": "<project><groupId>io.buildnote</groupId><artifactId>widget</artifactId>"
                       "<version>1.0.0</version><properties><kotlin.version>2.0.0</kotlin.version>"
                       "</properties></project>\n"
        })

        facts = self.collect(directory)

        self.assertEqual(facts["sources"], ["pom.xml"])
        self.assertEqual(facts["declared"], {"version": "2.0.0", "source": "pom.xml"})

    def test_collects_the_version_of_every_included_project(self):
        directory = self.workspace(**{
            "settings.gradle.kts": 'include("service")\ninclude("tools")\n',
            "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
            "service/build.gradle.kts": 'plugins { kotlin("jvm") version "2.1.0" }\n',
            "tools/build.gradle.kts": "plugins { }\n",
        })

        projects = self.collect(directory)["projects"]

        self.assertEqual([project["path"] for project in projects], [":", ":service", ":tools"])
        self.assertEqual(projects[0]["declared"], {"version": "2.0.0", "source": "build.gradle.kts"})
        self.assertEqual(
            projects[1]["declared"],
            {"version": "2.1.0", "source": "service/build.gradle.kts"},
        )
        self.assertIsNone(projects[2]["declared"])

    def test_declares_nothing_when_the_build_declares_no_version(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { }\n"})

        facts = self.collect(directory)

        self.assertIsNone(facts["declared"])

    def test_collects_nothing_for_a_directory_with_no_build(self):
        self.assertIsNone(self.collect(self.workspace()))

    def test_reports_a_directory_that_is_not_there(self):
        facts = self.collect(self.workspace(), projectDir="nowhere")

        self.assertFalse(facts["exists"])
        self.assertIn("nowhere is not a directory", facts["incomplete"])

    def test_collects_from_the_one_build_that_collected_anything(self):
        directory = self.workspace(**{"pom.xml": "<project/>\n"})
        environment = self.environment({"projectDir": "."})
        environment["GUARDRAIL_FACTS"] = self.facts_file({"maven": {"exists": True, "sources": ["pom.xml"]}})

        result = self.run_script(collector_script("kotlin"), directory, environment)

        self.assertEqual(result.code, 0, result.output)
        self.assertNotIn("incomplete", result.payload)
        self.assertTrue(result.payload["exists"])
        self.assertEqual(result.payload["sources"], ["pom.xml"])

    def test_collects_nothing_when_neither_build_collected_anything(self):
        directory = self.workspace(**{"build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n'})
        environment = self.environment({"projectDir": "."})
        environment["GUARDRAIL_FACTS"] = self.facts_file({})

        result = self.run_script(collector_script("kotlin"), directory, environment)

        self.assertEqual(result.code, 0, result.output)
        self.assertIsNone(result.payload)


if __name__ == "__main__":
    unittest.main()
