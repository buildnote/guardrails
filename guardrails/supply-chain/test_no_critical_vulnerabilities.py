#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)


def trivy(*vulnerabilities):
    return """{"SchemaVersion": 2, "Results": [{"Target": "build.gradle.kts", "Class": "lang-pkgs",
      "Vulnerabilities": [%s]}]}""" % ",".join(vulnerabilities)


def vulnerability(identifier, severity, package="log4j-core", fixed="2.15.0"):
    return """{"VulnerabilityID": "%s", "PkgName": "%s", "InstalledVersion": "2.14.1",
      "FixedVersion": "%s", "Severity": "%s", "Title": "a problem in %s"}""" % (
        identifier, package, fixed, severity, package)


SARIF = fixture("semgrep.sarif")


class NoCriticalVulnerabilitiesTest(GuardrailTestCase):
    SCRIPT = "no-critical-vulnerabilities.py"
    COLLECT = ["scan"]

    def test_passes_a_report_with_nothing_critical(self):
        self.assert_passed(self.check(self.workspace(**{"trivy.json": trivy(vulnerability("CVE-2024-1", "MEDIUM"))})))

    def test_fails_a_critical_vulnerability(self):
        self.assert_violation(
            self.check(self.workspace(**{"trivy.json": trivy(vulnerability("CVE-2021-44228", "CRITICAL"))})),
            "critical CVE-2021-44228 affects log4j-core 2.14.1",
        )

    def test_names_the_version_that_fixes_it(self):
        result = self.check(self.workspace(**{"trivy.json": trivy(vulnerability("CVE-2021-44228", "CRITICAL"))}))

        self.assertIn("fixed in 2.15.0", result.violations[0]["message"])

    def test_says_when_no_fix_is_named(self):
        report = trivy(vulnerability("CVE-2021-44228", "CRITICAL", fixed=""))
        result = self.check(self.workspace(**{"trivy.json": report}))

        self.assertIn("no fixed version named", result.violations[0]["message"])

    def test_gates_at_the_severity_it_is_given(self):
        workspace = self.workspace(**{"trivy.json": trivy(vulnerability("CVE-2024-1", "HIGH"))})

        self.assert_passed(self.check(workspace))
        self.assertEqual(self.check(workspace, severity="high").code, 1)

    def test_leaves_code_findings_to_the_security_guardrails(self):
        self.assert_passed(self.check(self.workspace(**{"semgrep.sarif": SARIF})))

    def test_leaves_out_an_identifier_it_is_told_to_ignore(self):
        report = trivy(vulnerability("CVE-2021-44228", "CRITICAL"))

        self.assert_passed(self.check(self.workspace(**{"trivy.json": report}), ignore="CVE-2021-44228"))

    def test_reports_every_critical_vulnerability(self):
        report = trivy(
            vulnerability("CVE-2021-44228", "CRITICAL"),
            vulnerability("CVE-2022-42889", "CRITICAL", package="commons-text"),
        )

        self.assertEqual(len(self.check(self.workspace(**{"trivy.json": report})).violations), 2)

    def test_skips_when_no_scanner_report_was_read(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "no scanner report matched")

    def test_skips_a_severity_nobody_recognises(self):
        report = trivy(vulnerability("CVE-2021-44228", "CRITICAL"))

        self.assert_skipped(
            self.check(self.workspace(**{"trivy.json": report}), severity="catastrophic"),
            "is not one of",
        )


if __name__ == "__main__":
    unittest.main()
