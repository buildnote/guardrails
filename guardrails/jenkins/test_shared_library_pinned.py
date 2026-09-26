#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

SHA = "1e204e9a9253d643386038d443f96446fa156a97"

BODY = fixture("body.Jenkinsfile")


def jenkinsfile(annotation="", step=""):
    heading = "%s _\n\n" % annotation if annotation else ""

    return heading + BODY % step


SCRIPTED = fixture("scripted.Jenkinsfile")


BARE_SCRIPTED = fixture("bare-scripted.Jenkinsfile")


class SharedLibraryPinnedTest(GuardrailTestCase):
    SCRIPT = "shared-library-pinned.py"
    COLLECT = ["jenkins"]

    def pipeline(self, text, **inputs):
        return self.check(self.workspace(Jenkinsfile=text), **inputs)

    def test_passes_a_library_pinned_to_a_version_tag(self):
        self.assert_passed(self.pipeline(jenkinsfile(annotation="@Library('company-shared@1.4.2')")))

    def test_passes_a_library_pinned_to_a_commit_sha(self):
        self.assert_passed(self.pipeline(jenkinsfile(annotation="@Library('company-shared@%s')" % SHA)))

    def test_passes_a_pipeline_that_loads_no_library(self):
        self.assert_passed(self.pipeline(jenkinsfile()))

    def test_fails_a_library_loaded_from_a_branch(self):
        self.assert_violation(
            self.pipeline(jenkinsfile(annotation="@Library('company-shared@main')")),
            "loads the shared library company-shared from main, which does not name a fixed revision",
        )

    def test_fails_a_library_loaded_with_no_version(self):
        self.assert_violation(
            self.pipeline(jenkinsfile(annotation="@Library('company-shared')")),
            "with no version, so it takes whatever the controller defaults to",
        )

    def test_fails_a_library_whose_ref_is_interpolated(self):
        self.assert_violation(
            self.pipeline(jenkinsfile(annotation='@Library("company-shared@${env.BRANCH_NAME}")')),
            "from ${env.BRANCH_NAME}, which does not name a fixed revision",
        )

    def test_fails_the_library_step_form(self):
        self.assert_violation(
            self.pipeline(jenkinsfile(step="library 'company-deploy@develop'")),
            "loads the shared library company-deploy from develop",
        )

    def test_reads_every_entry_of_a_list_annotation(self):
        result = self.pipeline(jenkinsfile(annotation="@Library(['company-shared@1.0.0', 'company-legacy@master'])"))

        self.assertEqual([violation["evidence"] for violation in result.violations], ["Jenkinsfile company-legacy"])

    def test_exempts_a_library_it_is_told_to_allow(self):
        self.assert_passed(
            self.pipeline(jenkinsfile(annotation="@Library('company-shared@main')"), allow="company-*")
        )

    def test_still_fails_a_library_no_glob_covers(self):
        self.assert_violation(
            self.pipeline(jenkinsfile(annotation="@Library('vendor-shared@main')"), allow="company-*"),
            "loads the shared library vendor-shared from main",
        )

    def test_names_the_jenkinsfile_it_found_it_in(self):
        result = self.pipeline(jenkinsfile(annotation="@Library('company-shared@main')"))

        self.assertIn("Jenkinsfile", result.violations[0]["evidence"])

    def test_reports_a_library_a_scripted_pipeline_names_where_it_can_be_read(self):
        self.assert_violation(self.pipeline(SCRIPTED), "loads the shared library company-shared from main")

    def test_skips_when_every_jenkinsfile_is_scripted_and_names_no_readable_library(self):
        self.assert_skipped(
            self.pipeline(BARE_SCRIPTED),
            "every Jenkinsfile that was read is a scripted pipeline declaring no library that could be read"
        )

    def test_still_reports_a_declarative_file_when_a_sibling_is_scripted(self):
        workspace = self.workspace(**{
            "Jenkinsfile": jenkinsfile(annotation="@Library('company-shared@main')"),
            "old.Jenkinsfile": BARE_SCRIPTED,
        })

        self.assert_violation(self.check(workspace), "loads the shared library company-shared from main")

    def test_skips_a_repository_with_no_jenkinsfile(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "no Jenkinsfile")


if __name__ == "__main__":
    unittest.main()
