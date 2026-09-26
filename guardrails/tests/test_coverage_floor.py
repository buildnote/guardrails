#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

JACOCO = fixture("jacoco.xml")

JACOCO_WITHOUT_BRANCHES = fixture("jacoco-without-branches.xml")

JACOCO_MEASURING_NOTHING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<report name="widget"/>
"""

LCOV = fixture("lcov.info")


class CoverageFloorTest(GuardrailTestCase):
    SCRIPT = "coverage-floor.py"
    COLLECT = ["coverage"]

    def test_passes_when_no_floor_is_configured(self):
        self.assert_passed(self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO})))

    def test_passes_coverage_at_the_line_floor(self):
        self.assert_passed(self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minLines="75"))

    def test_fails_coverage_under_the_line_floor(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minLines="90"),
            "Line coverage is 75.00%, under the 90% floor: 1 of the 4 lines measured are never executed",
        )

        self.assertEqual(violation["evidence"], "line coverage 75.00%")

    def test_names_the_least_covered_files_when_the_line_floor_is_missed(self):
        result = self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minLines="90")

        self.assertIn("least covered: com/company/widget/Queue.kt", result.output)

    def test_reads_the_line_floor_from_a_report_in_another_format(self):
        workspace = self.workspace(**{"lcov.info": LCOV})

        self.assert_passed(self.check(workspace, minLines="66"))
        self.assert_violation(
            self.check(workspace, minLines="90"),
            "Line coverage is 66.67%, under the 90% floor",
        )

    def test_fails_branch_coverage_under_the_branch_floor(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minBranches="50"),
            "Branch coverage is 25.00%, under the 50% floor: 3 of the 4 branches measured are never taken",
        )

        self.assertEqual(violation["evidence"], "branch coverage 25.00%")

    def test_passes_branch_coverage_at_the_branch_floor(self):
        self.assert_passed(self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minBranches="25"))

    def test_passes_a_jacoco_report_that_measured_no_branches_at_all(self):
        result = self.check(
            self.workspace(**{"jacocoTestReport.xml": JACOCO_WITHOUT_BRANCHES}), minBranches="80"
        )

        self.assert_passed(result)
        self.assertIn("the reports carry no branch coverage", result.output)

    def test_holds_the_line_floor_over_a_report_that_measured_no_branches(self):
        violation = self.assert_violation(
            self.check(
                self.workspace(**{"jacocoTestReport.xml": JACOCO_WITHOUT_BRANCHES}),
                minLines="90",
                minBranches="80",
            ),
            "Line coverage is 66.67%, under the 90% floor",
        )

        self.assertEqual(violation["evidence"], "line coverage 66.67%")

    def test_passes_a_format_that_carries_no_branch_coverage(self):
        result = self.check(self.workspace(**{"lcov.info": LCOV}), minBranches="80")

        self.assert_passed(result)
        self.assertIn("the reports carry no branch coverage", result.output)

    def test_passes_a_report_that_measured_nothing_at_all(self):
        result = self.check(
            self.workspace(**{"jacocoTestReport.xml": JACOCO_MEASURING_NOTHING}),
            minLines="80",
            minBranches="80",
        )

        self.assert_passed(result)
        self.assertIn("the reports measured no lines", result.output)

    def test_reports_both_floors_it_misses(self):
        result = self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minLines="90", minBranches="50")

        self.assertEqual(len(result.violations), 2)
        self.assertEqual(result.code, 1)

    def test_skips_when_no_coverage_report_was_published(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"}), minLines="80"),
            "no coverage report matched",
        )

    def test_skips_a_floor_that_is_not_a_number(self):
        self.assert_skipped(
            self.check(self.workspace(**{"jacocoTestReport.xml": JACOCO}), minLines="most of it"),
            "minLines 'most of it' is not a number",
        )


if __name__ == "__main__":
    unittest.main()
