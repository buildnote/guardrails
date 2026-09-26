#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

JUNIT = fixture("green.xml")

EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.company.widget.QueueTest" tests="0" failures="0" errors="0" skipped="0" time="0.000"/>
"""

CTRF = fixture("ctrf.json")


class ResultsPublishedTest(GuardrailTestCase):
    SCRIPT = "results-published.py"
    COLLECT = ["tests"]

    def test_passes_a_build_that_published_a_junit_report(self):
        self.assert_passed(self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT})))

    def test_passes_a_build_that_published_a_report_in_another_format(self):
        self.assert_passed(self.check(self.workspace(**{"jest-ctrf.json": CTRF})))

    def test_fails_a_build_that_published_no_report_at_all(self):
        self.assert_violation(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "The build produced no test report",
        )

    def test_says_what_it_looked_for_when_nothing_was_published(self):
        result = self.check(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(result.code, 1)
        self.assertIn("TEST-*.xml", result.violations[0]["message"])
        self.assertEqual(result.violations[0]["evidence"], "no test report")

    def test_fails_a_report_naming_no_cases(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": EMPTY})),
            "The build published 1 test report naming 0 cases in total, fewer than the 1 this guardrail asks for",
        )

        self.assertEqual(violation["evidence"], "0 tests")

    def test_fails_a_report_naming_fewer_cases_than_it_is_asked_for(self):
        workspace = self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT})

        self.assert_passed(self.check(workspace))
        self.assert_violation(
            self.check(workspace, minTests="5"),
            "The build published 1 test report naming 2 cases in total, fewer than the 5 this guardrail asks for",
        )

    def test_skips_a_minimum_that_is_not_a_number(self):
        self.assert_skipped(
            self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT}), minTests="lots"),
            "minTests 'lots' is not a number",
        )


if __name__ == "__main__":
    unittest.main()
