#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

DEPS = fixture("deps.edn")

LOCAL = DEPS.replace(
    "ring/ring-core {:mvn/version \"1.12.1\"}",
    "company/protocol {:local/root \"../protocol\"}",
)

LOCAL_ALIAS = DEPS.replace(
    "lambdaisland/kaocha {:mvn/version \"1.91.1392\"}",
    "company/fixtures {:local/root \"../fixtures\"}",
)

PROJECT = fixture("project.clj")


class NoLocalDependenciesTest(GuardrailTestCase):
    SCRIPT = "no-local-dependencies.py"
    COLLECT = ["clojure"]

    def test_passes_a_project_resolving_everything_from_a_repository(self):
        self.assert_passed(self.check(self.workspace(**{"deps.edn": DEPS})))

    def test_passes_a_leiningen_project(self):
        self.assert_passed(self.check(self.workspace(**{"project.clj": PROJECT})))

    def test_fails_a_dependency_taken_from_a_local_root(self):
        directory = self.workspace(**{"deps.edn": LOCAL})

        violation = self.assert_violation(
            self.check(directory),
            "deps.edn takes company/protocol from a :local/root, so the build compiles a directory outside the checkout",
        )

        self.assertEqual(violation["evidence"], "company/protocol (deps.edn)")

    def test_fails_a_local_dependency_an_alias_adds(self):
        directory = self.workspace(**{"deps.edn": LOCAL_ALIAS})

        self.assert_violation(self.check(directory), "deps.edn takes company/fixtures from a :local/root")

    def test_skips_a_manifest_that_could_not_be_read(self):
        directory = self.workspace(**{"deps.edn": "{:deps {org.clojure/clojure {:mvn/version \"1.11.3\"}\n"})

        self.assert_skipped(self.check(directory), "no manifest in . could be read as a Clojure build")

    def test_skips_a_directory_with_no_clojure_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Clojure build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"deps.edn": DEPS}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"service/deps.edn": LOCAL})

        self.assert_violation(self.check(directory, projectDir="service"), "takes company/protocol from a :local/root")


if __name__ == "__main__":
    unittest.main()
