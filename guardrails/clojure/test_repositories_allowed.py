#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

DEPS = fixture("deps.edn")

WITHOUT_REPOSITORIES = fixture("without-repositories.edn")

INTERNAL = DEPS.replace(
    ":mvn/repos {\"clojars\" {:url \"https://repo.clojars.org/\"}}",
    ":mvn/repos {\"internal\" {:url \"https://nexus.internal.example.com/repository/maven\"}}",
)

LOOKALIKE = DEPS.replace(
    ":mvn/repos {\"clojars\" {:url \"https://repo.clojars.org/\"}}",
    ":mvn/repos {\"clojars\" {:url \"https://clojars.org.evil.example/repo\"}}",
)

WITHOUT_URL = DEPS.replace(
    ":mvn/repos {\"clojars\" {:url \"https://repo.clojars.org/\"}}",
    ":mvn/repos {\"internal\" {}}",
)

PROJECT = fixture("project.clj")


class RepositoriesAllowedTest(GuardrailTestCase):
    SCRIPT = "repositories-allowed.py"
    COLLECT = ["clojure"]

    def test_passes_a_project_resolving_from_an_allowed_host(self):
        self.assert_passed(self.check(self.workspace(**{"deps.edn": DEPS})))

    def test_passes_a_project_that_adds_no_repository(self):
        self.assert_passed(self.check(self.workspace(**{"deps.edn": WITHOUT_REPOSITORIES})))

    def test_fails_a_repository_on_a_host_nobody_allowed(self):
        directory = self.workspace(**{"deps.edn": INTERNAL})

        violation = self.assert_violation(
            self.check(directory),
            "The repository internal resolves from nexus.internal.example.com, which is not a host the team allows",
        )

        self.assertEqual(violation["evidence"], "internal (nexus.internal.example.com)")

    def test_fails_a_host_that_only_reads_like_an_allowed_one(self):
        directory = self.workspace(**{"deps.edn": LOOKALIKE})

        self.assert_violation(self.check(directory), "resolves from clojars.org.evil.example")

    def test_fails_a_repository_that_names_no_url(self):
        directory = self.workspace(**{"deps.edn": WITHOUT_URL})

        violation = self.assert_violation(
            self.check(directory),
            "The repository internal in deps.edn names no host to resolve from",
        )

        self.assertEqual(violation["evidence"], "internal (deps.edn)")

    def test_honours_the_hosts_it_is_given(self):
        directory = self.workspace(**{"deps.edn": INTERNAL})

        self.assert_passed(self.check(directory, allowedHosts="nexus.internal.example.com,repo1.maven.org"))
        self.assert_violation(self.check(directory, allowedHosts="repo1.maven.org"), "resolves from nexus")

    def test_skips_when_no_host_is_named_as_allowed(self):
        directory = self.workspace(**{"deps.edn": INTERNAL})

        self.assert_skipped(self.check(directory, allowedHosts=","), "no repository host was named")

    def test_skips_a_leiningen_project_whose_repositories_are_not_read(self):
        directory = self.workspace(**{"project.clj": PROJECT})

        self.assert_skipped(self.check(directory), "project.clj is Clojure read by pattern")

    def test_skips_a_manifest_that_could_not_be_read(self):
        directory = self.workspace(**{"deps.edn": "{:deps {org.clojure/clojure {:mvn/version \"1.11.3\"}\n"})

        self.assert_skipped(self.check(directory), "no manifest in . could be read as a Clojure build")

    def test_skips_a_directory_with_no_clojure_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Clojure build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.workspace(**{"deps.edn": DEPS}), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"service/deps.edn": INTERNAL})

        self.assert_violation(self.check(directory, projectDir="service"), "resolves from nexus.internal.example.com")


if __name__ == "__main__":
    unittest.main()
