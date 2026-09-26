#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

NONE_SKIPPED = fixture("green.xml")

ONE_SKIPPED = fixture("one-skipped.xml")

TWO_SKIPPED = fixture("two-skipped.xml")

FAILING = fixture("failing.xml")


class NoSkippedGrowthTest(GuardrailTestCase):
    SCRIPT = "no-skipped-growth.py"
    COLLECT = ["tests"]

    def test_passes_a_build_that_skipped_nothing(self):
        self.assert_passed(self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": NONE_SKIPPED})))

    def test_leaves_a_failing_test_to_the_failures_guardrail(self):
        self.assert_passed(self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": FAILING})))

    def test_fails_a_build_that_skipped_a_test_when_the_budget_is_none(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": ONE_SKIPPED})),
            "1 test skipped, over the budget of 0 this guardrail is configured with",
        )

        self.assertEqual(violation["evidence"], "1 test skipped")

    def test_passes_a_build_within_the_budget_it_is_given(self):
        workspace = self.workspace(**{"TEST-com.company.widget.QueueTest.xml": TWO_SKIPPED})

        self.assertEqual(self.check(workspace).code, 1)
        self.assert_passed(self.check(workspace, maxSkipped="2"))

    def test_fails_a_build_over_the_budget_it_is_given(self):
        self.assert_violation(
            self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": TWO_SKIPPED}), maxSkipped="1"),
            "2 tests skipped, over the budget of 1 this guardrail is configured with",
        )

    def test_names_the_skipped_cases(self):
        result = self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": TWO_SKIPPED}))

        self.assertIn("skipped: drops the oldest under load, connects to the broker", result.output)

    def test_skips_when_no_test_report_was_published(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"}), maxSkipped="2"),
            "no test report matched",
        )

    def test_skips_a_budget_that_is_not_a_number(self):
        self.assert_skipped(
            self.check(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": TWO_SKIPPED}), maxSkipped="a few"),
            "maxSkipped 'a few' is not a number",
        )


if __name__ == "__main__":
    unittest.main()
