#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

GREEN = fixture("green.xml")

RED = fixture("red.xml")

SKIPPED_ONLY = fixture("skipped-only.xml")


def junit_with(failures):
    cases = "".join(
        """<testcase name="fails %d" classname="com.company.widget.QueueTest" time="0.001">
             <failure message="nope %d"/>
           </testcase>""" % (number, number)
        for number in range(failures)
    )

    return """<testsuite name="com.company.widget.QueueTest" time="1.0">%s</testsuite>""" % cases


class NoFailuresTest(GuardrailTestCase):
    SCRIPT = "no-failures.py"
    COLLECT = ["tests"]

    def test_passes_a_build_whose_tests_all_passed(self):
        self.assert_passed(self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": GREEN})))

    def test_passes_a_build_that_only_skipped_a_test(self):
        self.assert_passed(self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": SKIPPED_ONLY})))

    def test_reports_the_failed_and_the_errored_case(self):
        result = self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": RED}))

        self.assertEqual(result.code, 1)
        self.assertEqual(
            result.messages,
            [
                "The test rejects a negative limit in com.company.widget.QueueTest failed",
                "The test connects to the broker in com.company.widget.BrokerTest ended in an error",
            ],
        )

    def test_locates_each_failing_case_by_its_suite_and_name(self):
        result = self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": RED}))

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            [
                "com.company.widget.QueueTest.rejects a negative limit",
                "com.company.widget.BrokerTest.connects to the broker",
            ],
        )

    def test_says_how_many_failing_cases_the_collector_left_out(self):
        result = self.check(self.workspace(**{"junit.xml": junit_with(60)}))

        self.assertEqual(len(result.violations), 50)
        self.assertEqual(result.code, 1)
        self.assertIn("10 of the 60 failing cases were left out of the facts by the collector", result.output)

    def test_says_nothing_about_dropped_cases_when_none_were_dropped(self):
        result = self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": RED}))

        self.assertNotIn("left out of the facts", result.output)

    def test_skips_when_no_test_report_was_published(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no test report matched",
        )


if __name__ == "__main__":
    unittest.main()
