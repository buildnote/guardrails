#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

DOCKERFILE = "FROM alpine@sha256:aaaa\nRUN apk add curl\nUSER root\n"


def report(*results):
    return fixture("hadolint-report.json") % ",".join(results)


def result(rule, level, text, line):
    return fixture("hadolint-result.json") % (rule, level, text, line)


ERROR = result("DL3002", "error", "Last USER should not be root.", 3)
WARNING = result("DL3008", "warning", "Pin versions in apk add.", 2)


class DockerfileLintCleanTest(GuardrailTestCase):
    SCRIPT = "lint-clean.py"
    COLLECT = ["docker"]

    def workspace_with(self, *results):
        return self.workspace(Dockerfile=DOCKERFILE, **{"hadolint.sarif": report(*results)})

    def test_passes_a_report_with_no_findings(self):
        self.assert_passed(self.check(self.workspace_with()))

    def test_fails_a_finding_at_the_gated_severity(self):
        violation = self.assert_violation(self.check(self.workspace_with(ERROR)), "high lint finding DL3002")

        self.assertEqual(violation["evidence"], "Dockerfile:3 DL3002")

    def test_passes_a_finding_below_the_gate(self):
        self.assert_passed(self.check(self.workspace_with(WARNING)))

    def test_gates_lower_when_it_is_told_to(self):
        self.assert_violation(self.check(self.workspace_with(WARNING), severity="medium"), "DL3008")

    def test_ignores_the_rules_it_is_told_to(self):
        self.assert_passed(self.check(self.workspace_with(ERROR), ignore="DL3002"))

    def test_skips_when_no_linter_report_was_read(self):
        self.assert_skipped(self.check(self.workspace(Dockerfile=DOCKERFILE)), "no hadolint report")

    def test_skips_an_unknown_severity(self):
        self.assert_skipped(self.check(self.workspace_with(ERROR), severity="blocker"), "is not one of")


if __name__ == "__main__":
    unittest.main()
