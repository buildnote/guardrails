#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

DEPS = fixture("deps.edn")

WITHOUT_CLOJURE = fixture("without-clojure.edn")

PROJECT = fixture("project.clj")

PROJECT_WITHOUT_CLOJURE = fixture("project-without-clojure.clj")


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["clojure"]

    def test_passes_a_project_that_depends_on_clojure(self):
        self.assert_passed(self.check(self.workspace(**{"deps.edn": DEPS})))

    def test_passes_a_leiningen_project_that_depends_on_clojure(self):
        self.assert_passed(self.check(self.workspace(**{"project.clj": PROJECT})))

    def test_fails_a_project_that_depends_on_none(self):
        directory = self.workspace(**{"deps.edn": WITHOUT_CLOJURE})

        violation = self.assert_violation(self.check(directory), "No Clojure version declared in deps.edn")

        self.assertEqual(violation["evidence"], "deps.edn")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"deps.edn": DEPS.replace("1.11.3", "1.9.0")})

        violation = self.assert_violation(self.check(directory), "asks for Clojure 1.9.0, older than the 1.11 expected")

        self.assertEqual(violation["evidence"], "deps.edn (Clojure 1.9.0)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"deps.edn": DEPS})

        self.assert_passed(self.check(directory, minVersion="1.11.3"))
        self.assert_violation(self.check(directory, minVersion="1.12"), "older than the 1.12 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"deps.edn": DEPS.replace("1.11.3", "1.12")})

        self.assert_passed(self.check(directory, minVersion="1.12.0"))
        self.assert_violation(self.check(directory, minVersion="1.12.1"), "older than the 1.12.1 expected")

    def test_skips_a_leiningen_project_that_depends_on_no_clojure(self):
        directory = self.workspace(**{"project.clj": PROJECT_WITHOUT_CLOJURE})

        self.assert_skipped(self.check(directory), "project.clj is Clojure read by pattern")

    def test_skips_a_manifest_that_could_not_be_read(self):
        directory = self.workspace(**{"deps.edn": "{:deps {org.clojure/clojure {:mvn/version \"1.11.3\"}\n"})

        self.assert_skipped(self.check(directory), "no manifest in . could be read as a Clojure build")

    def test_skips_a_directory_with_no_clojure_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Clojure build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"deps.edn": DEPS}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"service/deps.edn": DEPS})

        self.assert_passed(self.check(directory, projectDir="service"))


if __name__ == "__main__":
    unittest.main()
