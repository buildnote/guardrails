#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

POM = fixture("dependencies-versioned-pom.xml")

MODULE_POM = fixture("dependencies-versioned-module-pom.xml")

SNAPSHOT = POM.replace("<slf4j.version>2.0.13</slf4j.version>", "<slf4j.version>2.1.0-SNAPSHOT</slf4j.version>")

SNAPSHOT_IN_A_PROFILE = POM.replace("<version>23.1.2</version>", "<version>23.2.0-SNAPSHOT</version>")

SNAPSHOT_BOM = POM.replace("<version>5.10.2</version>", "<version>5.11.0-SNAPSHOT</version>")

SNAPSHOT_IN_A_MODULE = MODULE_POM.replace(
    "      <groupId>org.postgresql</groupId>\n      <artifactId>postgresql</artifactId>\n"
    "      <version>42.7.3</version>",
    "      <groupId>com.company</groupId>\n      <artifactId>queue</artifactId>\n"
    "      <version>1.4.0-SNAPSHOT</version>",
)

MODULE = "service/pom.xml"


class NoSnapshotDependenciesTest(GuardrailTestCase):
    SCRIPT = "no-snapshot-dependencies.py"
    COLLECT = ["maven"]

    def build(self, **files):
        return self.workspace(**dict({"pom.xml": POM, MODULE: MODULE_POM}, **files))

    def test_passes_a_build_on_released_versions(self):
        self.assert_passed(self.check(self.build()))

    def test_logs_how_many_dependencies_it_read(self):
        result = self.check(self.workspace(**{"pom.xml": POM}))

        self.assertIn("read 5 declared dependencies, none at a snapshot version", result.output)

    def test_fails_a_snapshot_a_property_resolves_to(self):
        directory = self.build(**{"pom.xml": SNAPSHOT})

        violation = self.assert_violation(
            self.check(directory), "The dependency org.slf4j:slf4j-api is at 2.1.0-SNAPSHOT in pom.xml"
        )

        self.assertEqual(violation["evidence"], "org.slf4j:slf4j-api 2.1.0-SNAPSHOT (pom.xml)")

    def test_names_the_profile_that_declared_it(self):
        directory = self.build(**{"pom.xml": SNAPSHOT_IN_A_PROFILE})

        violation = self.assert_violation(self.check(directory), "in pom.xml under profile native")

        self.assertEqual(
            violation["evidence"], "org.graalvm.sdk:graal-sdk 23.2.0-SNAPSHOT (pom.xml under profile native)"
        )

    def test_names_the_module_that_declared_it(self):
        directory = self.build(**{MODULE: SNAPSHOT_IN_A_MODULE})

        violation = self.assert_violation(self.check(directory), "com.company:queue is at 1.4.0-SNAPSHOT in %s" % MODULE)

        self.assertEqual(violation["evidence"], "com.company:queue 1.4.0-SNAPSHOT (%s)" % MODULE)

    def test_fails_a_bom_imported_at_a_snapshot(self):
        result = self.check(self.workspace(**{"pom.xml": SNAPSHOT_BOM}))

        self.assertEqual(len(result.violations), 2)
        self.assertIn("The BOM org.junit:junit-bom is at 5.11.0-SNAPSHOT in pom.xml", result.messages[0])
        self.assertIn("The dependency org.junit.jupiter:junit-jupiter is at 5.11.0-SNAPSHOT", result.messages[1])

    def test_skips_a_pom_that_could_not_be_parsed(self):
        directory = self.workspace(**{"pom.xml": POM.replace("</project>", "")})

        self.assert_skipped(self.check(directory), "could not be parsed")

    def test_skips_a_directory_with_no_maven_build(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { kotlin(\"jvm\") }\n"})

        self.assert_skipped(self.check(directory), "no Maven build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"app/pom.xml": SNAPSHOT})

        self.assert_skipped(self.check(directory), "no Maven build in .")
        self.assert_violation(self.check(directory, projectDir="app"), "org.slf4j:slf4j-api is at 2.1.0-SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
