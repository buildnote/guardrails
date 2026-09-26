#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

SARIF = """{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "Semgrep OSS", "version": "1.86.0"}},
  "results": []}]}"""

TRIVY = """{"SchemaVersion": 2, "Results": [{"Target": "go.sum", "Vulnerabilities": []}]}"""


class ScanResultsPresentTest(GuardrailTestCase):
    SCRIPT = "scan-results-present.py"
    COLLECT = ["scan"]

    def test_passes_a_build_that_scanned_and_found_nothing(self):
        self.assert_passed(self.check(self.workspace(**{"semgrep.sarif": SARIF})))

    def test_passes_a_build_that_scanned_its_dependencies(self):
        self.assert_passed(self.check(self.workspace(**{"trivy.json": TRIVY})))

    def test_fails_a_build_that_produced_no_report_at_all(self):
        self.assert_violation(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "The build produced no security scan report",
        )

    def test_says_what_it_looked_for_when_it_fails(self):
        result = self.check(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(result.code, 1)
        self.assertIn("*.sarif", result.violations[0]["message"])

    def test_fails_a_report_that_could_not_be_read(self):
        self.assert_violation(
            self.check(self.workspace(**{"semgrep.sarif": "{ not json"})),
            "The build produced no security scan report",
        )

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"semgrep.sarif": SARIF})

        self.assert_passed(self.check(workspace))
        self.assertEqual(self.check(workspace, reports="trivy*.json").code, 1)


if __name__ == "__main__":
    unittest.main()
