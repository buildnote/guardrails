#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)


def sarif(*results):
    return """{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "Semgrep OSS", "version": "1.86.0"}},
      "results": [%s]}]}""" % ",".join(results)


def result(rule, level, path, line):
    return """{"ruleId": "%s", "level": "%s", "message": {"text": "%s is a problem"},
      "locations": [{"physicalLocation": {"artifactLocation": {"uri": "%s"},
      "region": {"startLine": %d}}}]}""" % (rule, level, rule, path, line)


TRIVY = fixture("trivy.json")


class NoHighFindingsTest(GuardrailTestCase):
    SCRIPT = "no-high-findings.py"
    COLLECT = ["scan"]

    def test_passes_a_report_with_nothing_at_the_gate(self):
        report = sarif(result("style.rule", "note", "src/Main.kt", 3))

        self.assert_passed(self.check(self.workspace(**{"semgrep.sarif": report})))

    def test_fails_a_finding_at_the_gate(self):
        report = sarif(result("insecure.hostname.verifier", "error", "src/Http.kt", 12))

        self.assert_violation(
            self.check(self.workspace(**{"semgrep.sarif": report})),
            "high finding insecure.hostname.verifier in src/Http.kt",
        )

    def test_fails_a_finding_above_the_gate(self):
        report = sarif(result("critical.rule", "error", "src/Http.kt", 12))
        result_at_default = self.check(self.workspace(**{"semgrep.sarif": report}), severity="medium")

        self.assertEqual(result_at_default.code, 1)

    def test_passes_a_finding_below_the_gate(self):
        report = sarif(result("warned.rule", "warning", "src/Http.kt", 12))

        self.assert_passed(self.check(self.workspace(**{"semgrep.sarif": report})))

    def test_gates_at_the_severity_it_is_given(self):
        report = sarif(result("warned.rule", "warning", "src/Http.kt", 12))
        workspace = self.workspace(**{"semgrep.sarif": report})

        self.assert_passed(self.check(workspace))
        self.assertEqual(self.check(workspace, severity="medium").code, 1)

    def test_leaves_dependency_findings_to_the_supply_chain_guardrails(self):
        self.assert_passed(self.check(self.workspace(**{"trivy.json": TRIVY})))

    def test_gates_on_a_dependency_finding_when_asked_to(self):
        result_for_sca = self.check(self.workspace(**{"trivy.json": TRIVY}), kinds="sca")

        self.assertEqual(result_for_sca.code, 1)

    def test_reports_every_finding_at_the_gate(self):
        report = sarif(
            result("first.rule", "error", "src/One.kt", 1),
            result("second.rule", "error", "src/Two.kt", 2),
        )

        self.assertEqual(len(self.check(self.workspace(**{"semgrep.sarif": report})).violations), 2)

    def test_skips_when_no_scanner_report_was_read(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no scanner report matched",
        )

    def test_skips_a_severity_nobody_recognises(self):
        report = sarif(result("any.rule", "error", "src/Http.kt", 12))

        self.assert_skipped(
            self.check(self.workspace(**{"semgrep.sarif": report}), severity="catastrophic"),
            "severity 'catastrophic' is not one of",
        )


if __name__ == "__main__":
    unittest.main()
