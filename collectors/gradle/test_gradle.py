#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"
VERSION_CATALOG = "gradle/libs.versions.toml"
DISTRIBUTION = "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14-bin.zip\n"


class GradleCollectorTest(CollectorTestCase):
    COLLECTOR = "gradle"

    def test_collects_the_root_build(self):
        directory = self.workspace(**{
            "settings.gradle.kts": 'rootProject.name = "widget"\n',
            "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
        })

        facts = self.collect(directory)

        self.assertTrue(facts["exists"])
        self.assertEqual(facts["settings"], "settings.gradle.kts")
        self.assertEqual(facts["manifest"], "build.gradle.kts")
        self.assertEqual(facts["sources"], ["build.gradle.kts"])

    def test_collects_the_wrapper_and_the_distribution_it_pins(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: DISTRIBUTION,
        })

        wrapper = self.collect(directory)["wrapper"]

        self.assertTrue(wrapper["script"])
        self.assertEqual(wrapper["properties"], WRAPPER_PROPERTIES)
        self.assertEqual(wrapper["distributionUrl"], "https://services.gradle.org/distributions/gradle-8.14-bin.zip")
        self.assertEqual(wrapper["version"], "8.14")

    def test_collects_the_checksum_the_wrapper_pins_the_distribution_to(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: DISTRIBUTION + "distributionSha256Sum=61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa\n",
        })

        wrapper = self.collect(directory)["wrapper"]

        self.assertEqual(
            wrapper["distributionSha256Sum"],
            "61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa",
        )

    def test_reports_a_wrapper_that_pins_no_checksum(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: DISTRIBUTION,
        })

        self.assertIsNone(self.collect(directory)["wrapper"]["distributionSha256Sum"])

    def test_reports_a_wrapper_that_is_not_committed(self):
        wrapper = self.collect(self.workspace(**{"build.gradle.kts": "plugins { }\n"}))["wrapper"]

        self.assertFalse(wrapper["script"])
        self.assertIsNone(wrapper["properties"])
        self.assertIsNone(wrapper["distributionUrl"])

    def test_collects_the_included_projects(self):
        directory = self.workspace(**{
            "settings.gradle.kts": 'include("service")\ninclude(":tools:cli")\nincludeBuild("gradle/scripts")\n',
            "build.gradle.kts": "plugins { }\n",
            "service/build.gradle.kts": 'plugins { kotlin("jvm") version "2.1.0" }\n',
            "tools/cli/build.gradle.kts": "plugins { }\n",
        })

        projects = self.collect(directory)["projects"]

        self.assertEqual([project["path"] for project in projects], [":", ":service", ":tools:cli"])
        self.assertEqual(projects[1]["directory"], "service")
        self.assertEqual(projects[1]["manifest"], "service/build.gradle.kts")
        self.assertEqual(projects[2]["directory"], "tools/cli")

    def test_collects_the_version_catalog(self):
        directory = self.workspace(**{
            "build.gradle.kts": "plugins { }\n",
            VERSION_CATALOG: '[versions]\nkotlin = "2.0.20"\njunit = "5.11.0"\n\n[libraries]\njunit-api = { module = "org.junit.jupiter:junit-jupiter-api" }\n',
        })

        facts = self.collect(directory)

        self.assertEqual(facts["versionCatalog"], {"kotlin": "2.0.20", "junit": "5.11.0"})
        self.assertEqual(facts["sources"], ["build.gradle.kts", VERSION_CATALOG])

    def test_reads_the_groovy_dsl(self):
        directory = self.workspace(**{
            "build.gradle": "plugins { id 'org.jetbrains.kotlin.jvm' version '1.9.24' }\n"
        })

        facts = self.collect(directory)

        self.assertEqual(facts["manifest"], "build.gradle")
        self.assertEqual(facts["settings"], None)

    def test_collects_the_declared_dependencies(self):
        directory = self.workspace(**{
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": fixture("declared-dependencies.gradle.kts"),
            "service/build.gradle.kts": fixture("service-dependencies.gradle.kts"),
        })

        dependencies = self.collect(directory)["dependencies"]

        self.assertEqual(dependencies["transitive"], [])
        self.assertEqual(
            [(it["path"], it["version"]) for it in dependencies["direct"]],
            [
                ("org.slf4j:slf4j-api", "1.7.36"),
                ("org.junit:junit-bom", "5.11.0"),
                ("com.google.guava:guava", "33.0.0-jre"),
            ],
        )
        self.assertEqual(dependencies["direct"][0]["scopes"], ["implementation"])
        self.assertEqual(dependencies["direct"][0]["source"], "build.gradle.kts")
        self.assertEqual(dependencies["direct"][2]["source"], "service/build.gradle.kts")

    def test_reads_the_groovy_declaration_forms(self):
        directory = self.workspace(**{
            "build.gradle": fixture("groovy-dependencies.gradle"),
        })

        direct = self.collect(directory)["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"]) for it in direct],
            [("org.slf4j:slf4j-api", "1.7.36"), ("junit:junit", "4.13.2"), ("com.h2database:h2", None)],
        )

    def test_resolves_a_dependency_named_by_the_version_catalog(self):
        directory = self.workspace(**{
            "build.gradle.kts": 'dependencies {\n    testImplementation(libs.junit.jupiter)\n    implementation(libs.guava)\n    implementation(libs.missing.one)\n}\n',
            VERSION_CATALOG: fixture("libs.versions.toml"),
        })

        direct = self.collect(directory)["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"]) for it in direct],
            [("org.junit.jupiter:junit-jupiter", "5.11.0"), ("com.google.guava:guava", "33.0.0-jre")],
        )

    def test_collects_the_transitive_dependencies_a_lock_file_resolves(self):
        directory = self.workspace(**{
            "build.gradle.kts": 'dependencies {\n    implementation("org.slf4j:slf4j-api:1.7.+")\n}\n',
            "gradle.lockfile": (
                "# This is a Gradle generated file for dependency locking.\n"
                "org.slf4j:slf4j-api:1.7.36=compileClasspath,runtimeClasspath\n"
                "ch.qos.logback:logback-classic:1.5.6=runtimeClasspath\n"
                "empty=annotationProcessor\n"
            ),
        })

        facts = self.collect(directory)
        dependencies = facts["dependencies"]

        self.assertEqual(facts["lockfiles"], ["gradle.lockfile"])
        self.assertEqual(
            [(it["path"], it["version"]) for it in dependencies["direct"]],
            [("org.slf4j:slf4j-api", "1.7.36")],
        )
        self.assertEqual(
            [(it["path"], it["version"]) for it in dependencies["transitive"]],
            [("ch.qos.logback:logback-classic", "1.5.6")],
        )
        self.assertEqual(
            dependencies["direct"][0]["scopes"], ["implementation", "compileClasspath", "runtimeClasspath"]
        )
        self.assertEqual(dependencies["transitive"][0]["source"], "gradle.lockfile")

    def test_reads_the_legacy_dependency_lock_files(self):
        directory = self.workspace(**{
            "build.gradle": "dependencies { }\n",
            "gradle/dependency-locks/runtimeClasspath.lockfile": (
                "# Generated by Gradle\norg.slf4j:slf4j-api:1.7.36\n"
            ),
        })

        facts = self.collect(directory)

        self.assertEqual(facts["lockfiles"], ["gradle/dependency-locks/runtimeClasspath.lockfile"])
        self.assertEqual(facts["dependencies"]["direct"], [])
        self.assertEqual(facts["dependencies"]["transitive"][0]["scopes"], ["runtimeClasspath"])

    def test_takes_the_version_a_platform_supplies(self):
        directory = self.workspace(**{
            "build.gradle.kts": fixture("platform-dependencies.gradle.kts"),
        })

        direct = self.collect(directory)["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"], it.get("managedBy")) for it in direct if not it.get("platform")],
            [
                ("org.junit.jupiter:junit-jupiter-api", "6.0.3", "org.junit:junit-bom:6.0.3"),
                ("org.junit.platform:junit-platform-launcher", "6.0.3", "org.junit:junit-bom:6.0.3"),
                ("org.http4k:http4k-testing-approval", "6.57.2.0", "org.http4k:http4k-bom:6.57.2.0"),
                ("com.unmanaged:widget", None, None),
            ],
        )
        self.assertTrue(direct[0]["platform"])
        self.assertNotIn("managedBy", direct[0])

    def test_prefers_the_most_specific_platform_and_leaves_a_declared_version_alone(self):
        directory = self.workspace(**{
            "build.gradle.kts": fixture("most-specific-platform.gradle.kts"),
        })

        direct = [it for it in self.collect(directory)["dependencies"]["direct"] if not it.get("platform")]

        self.assertEqual(
            [(it["path"], it["version"], it.get("managedBy")) for it in direct],
            [
                ("com.company.data:store", "2.0.0", "com.company.data:data-bom:2.0.0"),
                ("com.company.web:server", "1.0.0", "com.company:company-bom:1.0.0"),
                ("com.company.data:cache", "9.9.9", None),
            ],
        )

    def test_takes_the_version_a_root_platform_supplies_to_an_included_project(self):
        directory = self.workspace(**{
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": 'dependencies {\n    implementation(platform("org.http4k:http4k-bom:6.57.2.0"))\n}\n',
            "service/build.gradle.kts": 'dependencies {\n    implementation("org.http4k:http4k-core")\n}\n',
        })

        direct = [it for it in self.collect(directory)["dependencies"]["direct"] if not it.get("platform")]

        self.assertEqual(
            [(it["path"], it["version"], it.get("managedBy")) for it in direct],
            [("org.http4k:http4k-core", "6.57.2.0", "org.http4k:http4k-bom:6.57.2.0")],
        )

    def module_under_a_root(self, **files):
        root = self.workspace(**dict({
            "settings.gradle.kts": 'include("service")\n',
            "build.gradle.kts": 'dependencies {\n    implementation(platform("org.http4k:http4k-bom:6.57.2.0"))\n}\n',
            "gradlew": "#!/bin/sh\n",
            WRAPPER_PROPERTIES: DISTRIBUTION,
            VERSION_CATALOG: '[versions]\nkotlin = "2.0.0"\n',
            "service/build.gradle.kts":
                'dependencies {\n    implementation("org.http4k:http4k-core")\n}\n',
        }, **files))

        return root, os.path.join(root, "service")

    def test_reads_the_root_of_the_build_from_above_the_module(self):
        root, module = self.module_under_a_root()
        self.rooted_at(root)

        facts = self.collect(module)

        self.assertEqual(facts["directory"], "service")
        self.assertEqual(facts["root"], ".")
        self.assertEqual(facts["settings"], "settings.gradle.kts")
        self.assertEqual(facts["manifest"], "service/build.gradle.kts")
        self.assertEqual(
            facts["sources"],
            ["service/build.gradle.kts", "build.gradle.kts", VERSION_CATALOG],
        )
        self.assertEqual(facts["versionCatalog"], {"kotlin": "2.0.0"})
        self.assertEqual(facts["projects"], [{
            "path": ":",
            "directory": "service",
            "manifest": "service/build.gradle.kts",
        }])

    def test_states_every_path_from_the_directory_the_cli_runs_in(self):
        root, module = self.module_under_a_root()
        self.rooted_at(root)

        self.assertNotIn("..", json.dumps(self.collect(module)))

    def test_takes_the_wrapper_of_the_root_for_a_module_that_carries_none(self):
        root, module = self.module_under_a_root()
        self.rooted_at(root)

        wrapper = self.collect(module)["wrapper"]

        self.assertTrue(wrapper["script"])
        self.assertEqual(wrapper["properties"], WRAPPER_PROPERTIES)
        self.assertEqual(wrapper["version"], "8.14")

    def test_takes_the_version_a_root_platform_supplies_to_a_module_collected_on_its_own(self):
        root, module = self.module_under_a_root()
        self.rooted_at(root)

        direct = self.collect(module)["dependencies"]["direct"]

        self.assertEqual(
            [(it["path"], it["version"], it.get("managedBy")) for it in direct],
            [("org.http4k:http4k-core", "6.57.2.0", "org.http4k:http4k-bom:6.57.2.0")],
        )

    def test_leaves_the_root_alone_for_a_module_declaring_settings_of_its_own(self):
        root, module = self.module_under_a_root(**{
            "service/settings.gradle.kts": 'rootProject.name = "service"\n',
        })
        self.rooted_at(root)

        facts = self.collect(module)

        self.assertIsNone(facts["root"])
        self.assertEqual(facts["settings"], "service/settings.gradle.kts")
        self.assertEqual(facts["versionCatalog"], {})
        self.assertIsNone(facts["dependencies"]["direct"][0]["version"])

    def test_never_reads_above_the_directory_the_cli_runs_in(self):
        root, module = self.module_under_a_root()
        self.rooted_at(module)

        facts = self.collect(module)

        self.assertIsNone(facts["root"])
        self.assertIsNone(facts["settings"])
        self.assertIsNone(facts["dependencies"]["direct"][0]["version"])

    def test_ignores_a_constrained_and_a_commented_out_dependency(self):
        directory = self.workspace(**{
            "build.gradle.kts": fixture("constrained-and-commented.gradle.kts"),
        })

        direct = self.collect(directory)["dependencies"]["direct"]

        self.assertEqual([it["path"] for it in direct], ["org.real:dependency"])

    def test_reports_a_build_that_locks_nothing(self):
        facts = self.collect(self.workspace(**{"build.gradle.kts": "plugins { }\n"}))

        self.assertEqual(facts["lockfiles"], [])
        self.assertEqual(facts["dependencies"]["direct"], [])
        self.assertEqual(facts["dependencies"]["transitive"], [])

    def test_collects_nothing_for_a_project_that_is_not_a_gradle_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_directory_that_does_not_exist(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "service/build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n'
        })

        facts = self.collect(directory, projectDir="service")

        self.assertEqual(facts["directory"], "service")
        self.assertEqual(facts["manifest"], "service/build.gradle.kts")


if __name__ == "__main__":
    unittest.main()
