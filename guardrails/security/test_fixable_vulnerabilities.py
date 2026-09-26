#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def trivy(*vulnerabilities):
    return """{"SchemaVersion": 2, "Results": [{"Target": "go.sum", "Class": "lang-pkgs",
      "Vulnerabilities": [%s]}]}""" % ",".join(vulnerabilities)


def vulnerability(identifier, package, version, severity, fixed=None):
    fix = ', "FixedVersion": "%s"' % fixed if fixed else ""

    return """{"VulnerabilityID": "%s", "PkgName": "%s", "InstalledVersion": "%s",
      "Severity": "%s", "Title": "%s in %s"%s}""" % (identifier, package, version, severity, identifier, package, fix)


FIXED = trivy(vulnerability("CVE-2021-44228", "log4j-core", "2.14.1", "CRITICAL", fixed="2.15.0"))
UNFIXED = trivy(vulnerability("CVE-2024-0001", "libmystery", "1.0.0", "CRITICAL"))
LOW_AND_FIXED = trivy(vulnerability("CVE-2024-0002", "libminor", "1.0.0", "LOW", fixed="1.0.1"))


class FixableVulnerabilitiesTest(GuardrailTestCase):
    SCRIPT = "fixable-vulnerabilities.py"
    COLLECT = ["scan"]

    def test_fails_a_finding_the_scanner_named_a_fix_for(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"trivy.json": FIXED})), "is fixed in 2.15.0, so it costs an upgrade"
        )

        self.assertEqual(violation["evidence"], "log4j-core 2.14.1 -> 2.15.0")

    def test_passes_a_finding_with_no_fix_available(self):
        self.assert_passed(self.check(self.workspace(**{"trivy.json": UNFIXED})))

    def test_passes_a_fixable_finding_below_the_gate(self):
        self.assert_passed(self.check(self.workspace(**{"trivy.json": LOW_AND_FIXED})))

    def test_gates_lower_when_it_is_told_to(self):
        directory = self.workspace(**{"trivy.json": LOW_AND_FIXED})

        violation = self.assert_violation(self.check(directory, severity="low"), "affects libminor 1.0.0")

        self.assertEqual(violation["evidence"], "libminor 1.0.0 -> 1.0.1")

    def test_reports_only_the_kinds_it_is_given(self):
        self.assert_passed(self.check(self.workspace(**{"trivy.json": FIXED}), kinds="sast"))

    def test_skips_when_no_scanner_report_was_read(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "")

    def test_skips_an_unknown_severity(self):
        self.assert_skipped(self.check(self.workspace(**{"trivy.json": FIXED}), severity="blocker"), "is not one of")


if __name__ == "__main__":
    unittest.main()
