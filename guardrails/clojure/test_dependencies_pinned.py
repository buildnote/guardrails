#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

DEPS = fixture("deps.edn")

MOVING = fixture("moving.edn")

WITHOUT_SHA = fixture("without-sha.edn")

LOCAL = fixture("local.edn")

UNPINNED_ALIAS = fixture("unpinned-alias.edn")

PROJECT = fixture("project.clj")


class DependenciesPinnedTest(GuardrailTestCase):
    SCRIPT = "dependencies-pinned.py"
    COLLECT = ["clojure"]

    def test_passes_a_project_where_every_dependency_names_a_release(self):
        self.assert_passed(self.check(self.workspace(**{"deps.edn": DEPS})))

    def test_passes_a_leiningen_project_that_pins_every_dependency(self):
        self.assert_passed(self.check(self.workspace(**{"project.clj": PROJECT})))

    def test_fails_a_dependency_that_asks_for_a_moving_version(self):
        directory = self.workspace(**{"deps.edn": MOVING})

        violation = self.assert_violation(
            self.check(directory),
            "The dependency cheshire/cheshire in deps.edn asks for RELEASE rather than one released version",
        )

        self.assertEqual(violation["evidence"], "cheshire/cheshire (deps.edn)")

    def test_fails_a_git_dependency_with_no_sha(self):
        directory = self.workspace(**{"deps.edn": WITHOUT_SHA})

        self.assert_violation(self.check(directory), "The dependency io.github.company/drift in deps.edn names no :git/sha")

    def test_fails_a_dependency_taken_from_a_local_root(self):
        directory = self.workspace(**{"deps.edn": LOCAL})

        self.assert_violation(self.check(directory), "The dependency company/local in deps.edn comes from a :local/root")

    def test_fails_a_dependency_an_alias_adds(self):
        directory = self.workspace(**{"deps.edn": UNPINNED_ALIAS})

        self.assert_violation(self.check(directory), "The dependency lambdaisland/kaocha in deps.edn asks for LATEST")

    def test_fails_a_leiningen_dependency_on_a_snapshot(self):
        directory = self.workspace(**{"project.clj": PROJECT.replace("1.12.1", "1.13.0-SNAPSHOT")})

        self.assert_violation(
            self.check(directory),
            "The dependency ring/ring-core in project.clj asks for 1.13.0-SNAPSHOT",
        )

    def test_reports_every_unpinned_dependency(self):
        directory = self.workspace(**{"deps.edn": MOVING.replace(
            "cheshire/cheshire {:mvn/version \"RELEASE\"}",
            "cheshire/cheshire {:mvn/version \"RELEASE\"}\n        company/local {:local/root \"../local\"}",
        )})

        result = self.check(directory)

        self.assertEqual(sorted(it["evidence"] for it in result.violations),
                         ["cheshire/cheshire (deps.edn)", "company/local (deps.edn)"])

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
