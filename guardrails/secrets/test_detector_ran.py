#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

GITLEAKS_VERSION = "gitleaks version 8.18.4"

CLEAN = """{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "gitleaks"}}, "results": []}]}"""

FOUND = fixture("found.sarif")

UNSCANNED = {"README.md": "widget\n"}


class DetectorRanTest(GuardrailTestCase):
    SCRIPT = "detector-ran.py"
    COLLECT = ["secrets"]

    def gitleaks(self, stdout=CLEAN, code=0):
        return self.shim("gitleaks", version=GITLEAKS_VERSION, responses=[["detect", stdout, "", code]])

    def test_passes_a_checkout_a_detector_reported_clean(self):
        self.assert_passed(self.check(self.workspace(**{"gitleaks.sarif": CLEAN})))

    def test_passes_a_checkout_the_detector_found_something_in(self):
        self.assert_passed(self.check(self.workspace(**{"gitleaks.sarif": FOUND})))

    def test_passes_when_the_collector_ran_the_detector_itself(self):
        self.gitleaks()

        self.assert_passed(self.check(self.workspace(**UNSCANNED)))

    def test_fails_a_checkout_nothing_scanned(self):
        violation = self.assert_violation(
            self.check(self.workspace(**UNSCANNED)),
            "Nothing looked for a credential in this checkout",
        )

        self.assertEqual(violation["evidence"], "no secret detector")

    def test_says_what_it_looked_for_and_what_to_install(self):
        result = self.check(self.workspace(**UNSCANNED))

        self.assertEqual(result.code, 1)
        self.assertIn("gitleaks*.sarif", result.violations[0]["message"])
        self.assertIn("brew install gitleaks", result.violations[0]["message"])

    def test_fails_a_detector_that_printed_nothing_it_could_read(self):
        self.gitleaks(stdout="Error: unknown flag --redact\n", code=2)

        self.assert_violation(self.check(self.workspace(**UNSCANNED)), "gitleaks exited with 2")

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"gitleaks.sarif": CLEAN})

        self.assert_passed(self.check(workspace))
        self.assertEqual(self.check(workspace, reports="trufflehog*.json").code, 1)


if __name__ == "__main__":
    unittest.main()
