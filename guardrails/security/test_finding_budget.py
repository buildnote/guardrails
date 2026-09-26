#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def sarif(*results):
    return """{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "Semgrep OSS", "version": "1.86.0"}},
      "results": [%s]}]}""" % ",".join(results)


def result(rule, level, path, line):
    return """{"ruleId": "%s", "level": "%s", "message": {"text": "%s is a problem"},
      "locations": [{"physicalLocation": {"artifactLocation": {"uri": "%s"},
      "region": {"startLine": %d}}}]}""" % (rule, level, rule, path, line)


def findings(count, level="warning"):
    return sarif(*[result("rule.%d" % it, level, "src/Main.kt", it) for it in range(1, count + 1)])


class FindingBudgetTest(GuardrailTestCase):
    SCRIPT = "finding-budget.py"
    COLLECT = ["scan"]

    def test_passes_a_report_within_the_budget(self):
        self.assert_passed(self.check(self.workspace(**{"semgrep.sarif": findings(3)})))

    def test_fails_a_report_past_the_budget(self):
        directory = self.workspace(**{"semgrep.sarif": findings(4)})

        violation = self.assert_violation(
            self.check(directory, budget=3), "carries 4 findings at or above medium, more than the 3"
        )

        self.assertEqual(violation["evidence"], "4 findings at or above medium")

    def test_counts_only_at_or_above_the_severity_it_is_given(self):
        directory = self.workspace(**{"semgrep.sarif": findings(4, level="note")})

        self.assert_passed(self.check(directory, budget=3))
        self.assert_violation(self.check(directory, severity="low", budget=3), "4 findings at or above low")

    def test_counts_only_the_kinds_it_is_given(self):
        directory = self.workspace(**{"semgrep.sarif": findings(4)})

        self.assert_passed(self.check(directory, budget=3, kinds="container"))

    def test_skips_when_no_scanner_report_was_read(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "")

    def test_skips_an_unknown_severity(self):
        directory = self.workspace(**{"semgrep.sarif": findings(1)})

        self.assert_skipped(self.check(directory, severity="blocker"), "is not one of")

    def test_skips_when_the_budget_is_not_a_number(self):
        directory = self.workspace(**{"semgrep.sarif": findings(1)})

        self.assert_skipped(self.check(directory, budget="a few"), "budget 'a few' is not a number")


if __name__ == "__main__":
    unittest.main()
