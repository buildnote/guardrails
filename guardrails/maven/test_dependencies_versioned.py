#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

POM = fixture("dependencies-versioned-pom.xml")

MODULE_POM = fixture("dependencies-versioned-module-pom.xml")

MANAGED_BY_A_PARENT = fixture("managed-by-a-parent.xml")

UNVERSIONED = POM.replace(
    "      <groupId>com.google.guava</groupId>\n      <artifactId>guava</artifactId>\n    </dependency>",
    "      <groupId>com.company</groupId>\n      <artifactId>queue</artifactId>\n    </dependency>",
)

UNVERSIONED_IN_A_PROFILE = POM.replace("          <version>23.1.2</version>\n", "")

UNVERSIONED_IN_A_MODULE = MODULE_POM.replace(
    "      <groupId>org.postgresql</groupId>\n      <artifactId>postgresql</artifactId>\n"
    "      <version>42.7.3</version>",
    "      <groupId>com.company</groupId>\n      <artifactId>queue</artifactId>",
)

MODULE = "service/pom.xml"


class DependenciesVersionedTest(GuardrailTestCase):
    SCRIPT = "dependencies-versioned.py"
    COLLECT = ["maven"]

    def build(self, **files):
        return self.workspace(**dict({"pom.xml": POM, MODULE: MODULE_POM}, **files))

    def test_passes_a_build_that_versions_every_dependency(self):
        self.assert_passed(self.check(self.build()))

    def test_passes_a_bom_whose_own_version_a_parent_outside_the_checkout_manages(self):
        self.assert_passed(self.check(self.workspace(**{"pom.xml": MANAGED_BY_A_PARENT})))

    def test_logs_how_many_dependencies_resolved(self):
        result = self.check(self.workspace(**{"pom.xml": POM}))

        self.assertIn("4 declared dependencies, every one resolving to a version", result.output)

    def test_fails_a_dependency_nothing_versions(self):
        directory = self.build(**{"pom.xml": UNVERSIONED})

        violation = self.assert_violation(self.check(directory), "com.company:queue in pom.xml takes no version")

        self.assertEqual(violation["evidence"], "com.company:queue (pom.xml)")

    def test_names_the_profile_that_declared_it(self):
        directory = self.build(**{"pom.xml": UNVERSIONED_IN_A_PROFILE})

        violation = self.assert_violation(self.check(directory), "in pom.xml under profile native")

        self.assertEqual(violation["evidence"], "org.graalvm.sdk:graal-sdk (pom.xml under profile native)")

    def test_names_the_module_that_declared_it(self):
        directory = self.build(**{MODULE: UNVERSIONED_IN_A_MODULE})

        violation = self.assert_violation(self.check(directory), "com.company:queue in %s" % MODULE)

        self.assertEqual(violation["evidence"], "com.company:queue (%s)" % MODULE)

    def test_skips_a_pom_that_could_not_be_parsed(self):
        directory = self.workspace(**{"pom.xml": POM.replace("</project>", "")})

        self.assert_skipped(self.check(directory), "could not be parsed")

    def test_skips_a_directory_with_no_maven_build(self):
        directory = self.workspace(**{"build.gradle.kts": "plugins { kotlin(\"jvm\") }\n"})

        self.assert_skipped(self.check(directory), "no Maven build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"app/pom.xml": UNVERSIONED})

        self.assert_skipped(self.check(directory), "no Maven build in .")
        self.assert_violation(
            self.check(directory, projectDir="app"),
            "com.company:queue in %s takes no version" % "app/pom.xml",
        )


if __name__ == "__main__":
    unittest.main()
