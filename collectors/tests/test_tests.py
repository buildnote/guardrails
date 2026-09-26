#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

JUNIT = fixture("junit.xml")

NUNIT = fixture("nunit.xml")

TRX = fixture("trx.xml")

CTRF = fixture("ctrf.json")

OTR = fixture("otr.xml")

JUNIT_SUITES = fixture("junit-suites.xml")

NUNIT3 = fixture("nunit3.xml")

TRX_RUN = fixture("trx-run.xml")

CTRF_RUN = fixture("ctrf-run.json")

OTR_EVENTS = fixture("otr-events.xml")

MALFORMED = (
    "",
    "   ",
    "not a report at all",
    "<testsuite><testcase",
    "<?xml version=\"1.0\"?><nothing/>",
    "[]",
    "{}",
    "{\"broken\": ",
)

COVERAGE_REPORTS = (
    fixture("jacoco-core.xml"),
    fixture("cobertura-outer.xml"),
    """{"src/app.js": {"statementMap": {"0": {"start": {"line": 1, "column": 0}}}, "s": {"0": 1}}}""",
    "SF:src/app.ts\nDA:1,1\nend_of_record\n",
)


def junit_with(failures, skips):
    cases = "".join(
        """<testcase name="fails %d" classname="Company.WidgetTests" time="0.001">
             <failure message="nope %d"/>
           </testcase>""" % (number, number)
        for number in range(failures)
    ) + "".join(
        """<testcase name="skips %d" classname="Company.WidgetTests" time="0.001">
             <skipped message="later %d"/>
           </testcase>""" % (number, number)
        for number in range(skips)
    )

    return """<testsuite name="Company.WidgetTests" time="1.0">%s</testsuite>""" % cases


class TestsTest(CollectorTestCase):
    COLLECTOR = "tests"

    def test_reads_a_junit_report(self):
        facts = self.collect(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["suites"], 1)
        self.assertEqual(facts["totals"], {
            "tests": 4,
            "passed": 1,
            "failed": 1,
            "errors": 1,
            "skipped": 1,
            "durationMs": 500,
        })
        self.assertEqual(facts["dropped"], 0)

    def test_carries_the_failed_and_errored_cases_only(self):
        facts = self.collect(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT}))

        self.assertEqual(
            facts["failures"],
            [
                {
                    "name": "rejects a negative limit",
                    "classname": "com.company.widget.QueueTest",
                    "status": "failed",
                    "file": None,
                },
                {
                    "name": "connects to the broker",
                    "classname": "com.company.widget.BrokerTest",
                    "status": "error",
                    "file": None,
                },
            ],
        )
        self.assertEqual(
            facts["skipped"],
            [
                {
                    "name": "drops the oldest under load",
                    "classname": "com.company.widget.QueueTest",
                    "status": "skipped",
                    "file": None,
                }
            ],
        )

    def test_names_every_report_it_read(self):
        facts = self.collect(self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "TEST-com.company.widget.QueueTest.xml")
        self.assertEqual(report["format"], "junit")
        self.assertIsNotNone(report["modified"])

    def test_reads_an_nunit_report(self):
        facts = self.collect(self.workspace(**{"test-results.xml": NUNIT}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["nunit"])
        self.assertEqual(facts["totals"]["tests"], 2)
        self.assertEqual(facts["totals"]["failed"], 1)
        self.assertEqual(facts["totals"]["durationMs"], 1500)
        self.assertEqual([failure["name"] for failure in facts["failures"]], ["Removes"])

    def test_reads_a_trx_report(self):
        facts = self.collect(self.workspace(**{"company.trx": TRX}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["trx"])
        self.assertEqual(facts["totals"]["failed"], 1)
        self.assertEqual(facts["failures"][0]["classname"], "Company.WidgetTests")

    def test_reads_a_ctrf_report(self):
        facts = self.collect(self.workspace(**{"jest-ctrf.json": CTRF}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["ctrf"])
        self.assertEqual(facts["totals"]["tests"], 2)
        self.assertEqual(facts["failures"][0]["file"], "src/App.test.tsx")

    def test_reads_an_open_test_report(self):
        facts = self.collect(self.workspace(**{"open-test-report.xml": OTR}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["otr"])
        self.assertEqual(facts["totals"]["passed"], 1)
        self.assertEqual(facts["failures"][0]["classname"], "com.company.widget.QueueTest")

    def test_merges_every_report_into_one_total(self):
        facts = self.collect(self.workspace(**{
            "TEST-com.company.widget.QueueTest.xml": JUNIT,
            "test-results.xml": NUNIT,
            "company.trx": TRX,
        }))

        self.assertEqual(facts["suites"], 3)
        self.assertEqual(len(facts["reports"]), 3)
        self.assertEqual(facts["totals"]["tests"], 7)
        self.assertEqual(facts["totals"]["failed"], 3)
        self.assertEqual(facts["totals"]["errors"], 1)
        self.assertEqual(facts["totals"]["durationMs"], 2123)

    def test_drops_cases_over_the_limit_but_keeps_the_totals_whole(self):
        facts = self.collect(self.workspace(**{"junit.xml": junit_with(9, 7)}), maxFailures="4")

        self.assertEqual(facts["totals"]["tests"], 16)
        self.assertEqual(facts["totals"]["failed"], 9)
        self.assertEqual(facts["totals"]["skipped"], 7)
        self.assertEqual(len(facts["failures"]), 4)
        self.assertEqual(len(facts["skipped"]), 4)
        self.assertEqual(facts["dropped"], 8)

    def test_ignores_a_report_it_cannot_read(self):
        facts = self.collect(self.workspace(**{
            "junit-broken.xml": "<testsuite name=\"widget\">",
            "TEST-com.company.widget.QueueTest.xml": JUNIT,
        }))

        self.assertEqual([report["path"] for report in facts["reports"]], ["TEST-com.company.widget.QueueTest.xml"])
        self.assertEqual(facts["totals"]["tests"], 4)

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no test report matched", facts["reason"])
        self.assertIn("TEST-*.xml", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"TEST-com.company.widget.QueueTest.xml": JUNIT, "jest-ctrf.json": CTRF})

        facts = self.collect(workspace, reports="*-ctrf.json")

        self.assertEqual([report["format"] for report in facts["reports"]], ["ctrf"])
        self.assertEqual(facts["totals"]["tests"], 2)

    def test_ignores_a_coverage_report_that_carries_no_cases(self):
        jacoco = """<report name="widget"><package name="com/company"></package></report>"""

        facts = self.collect(self.workspace(**{"test-results.xml": jacoco}))

        self.assertEqual(facts["source"], "none")

    def test_names_the_format_of_every_report(self):
        facts = self.collect(self.workspace(**{
            "junit.xml": JUNIT_SUITES,
            "test-results.xml": NUNIT3,
            "company.trx": TRX_RUN,
            "jest-ctrf.json": CTRF_RUN,
            "open-test-report.xml": OTR_EVENTS,
        }))

        self.assertEqual(
            [(report["path"], report["format"]) for report in facts["reports"]],
            [
                ("company.trx", "trx"),
                ("jest-ctrf.json", "ctrf"),
                ("junit.xml", "junit"),
                ("open-test-report.xml", "otr"),
                ("test-results.xml", "nunit"),
            ],
        )
        self.assertEqual(facts["totals"]["tests"], 18)

    def test_counts_a_mixed_junit_suite(self):
        facts = self.collect(self.workspace(**{"junit.xml": JUNIT_SUITES}))

        self.assertEqual(facts["totals"], {
            "tests": 4,
            "passed": 1,
            "failed": 1,
            "errors": 1,
            "skipped": 1,
            "durationMs": 412,
        })
        self.assertEqual(
            [(case["name"], case["status"]) for case in facts["failures"] + facts["skipped"]],
            [("test_divides_by_zero", "failed"), ("test_reads_configuration", "error"), ("test_uses_gpu", "skipped")],
        )

    def test_reads_the_details_of_a_junit_case(self):
        facts = self.collect(self.workspace(**{"junit.xml": JUNIT_SUITES}))

        self.assertEqual(facts["failures"][0], {
            "name": "test_divides_by_zero",
            "classname": "tests.test_calculator.CalculatorTests",
            "status": "failed",
            "file": "tests/test_calculator.py",
        })

    def test_sums_the_junit_cases_when_no_duration_is_stated(self):
        report = fixture("junit-no-duration.xml")

        facts = self.collect(self.workspace(**{"junit.xml": report}))

        self.assertEqual(facts["totals"]["durationMs"], 1000)

    def test_counts_a_junit_case_with_a_failure_and_an_error_as_failed(self):
        report = fixture("junit-failure-and-error.xml")

        facts = self.collect(self.workspace(**{"junit.xml": report}))

        self.assertEqual(facts["totals"]["failed"], 1)
        self.assertEqual(facts["totals"]["errors"], 0)
        self.assertEqual([failure["status"] for failure in facts["failures"]], ["failed"])

    def test_reads_a_junit_report_with_no_cases(self):
        facts = self.collect(self.workspace(**{"junit.xml": "<testsuites/>"}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["suites"], 1)
        self.assertEqual(facts["totals"]["tests"], 0)
        self.assertIsNone(facts["totals"]["durationMs"])

    def test_counts_nested_junit_suites_once(self):
        report = fixture("junit-nested-suites.xml")

        facts = self.collect(self.workspace(**{"junit.xml": report}))

        self.assertEqual(facts["totals"]["tests"], 1)

    def test_counts_a_version_three_nunit_run(self):
        facts = self.collect(self.workspace(**{"test-results.xml": NUNIT3}))

        self.assertEqual(facts["totals"], {
            "tests": 4,
            "passed": 2,
            "failed": 1,
            "errors": 0,
            "skipped": 1,
            "durationMs": 230,
        })
        self.assertEqual(facts["failures"], [{
            "name": "Divides_By_Zero",
            "classname": "DotnetTests.NUnitV3Tests.CalculatorTests",
            "status": "failed",
            "file": None,
        }])
        self.assertEqual([case["name"] for case in facts["skipped"]], ["Uses_External_Service"])

    def test_reads_a_version_two_nunit_run(self):
        report = fixture("nunit2-run.xml")

        facts = self.collect(self.workspace(**{"test-results.xml": report}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["nunit"])
        self.assertEqual(facts["totals"]["tests"], 3)
        self.assertEqual(facts["totals"]["failed"], 1)
        self.assertEqual(facts["totals"]["skipped"], 1)
        self.assertEqual(facts["totals"]["durationMs"], 34)
        self.assertEqual(
            [(case["name"], case["classname"]) for case in facts["failures"] + facts["skipped"]],
            [("FailingTest", "NUnit.Tests.MockTestFixture"), ("IgnoreTest", "NUnit.Tests.MockTestFixture")],
        )

    def test_keeps_a_parameterised_version_two_nunit_name_together(self):
        report = fixture("nunit2-parameterised.xml")

        facts = self.collect(self.workspace(**{"test-results.xml": report}))

        self.assertEqual(facts["failures"][0]["name"], "IsEven(i: 2.3)")
        self.assertEqual(facts["failures"][0]["classname"], "NUnit.Tests.MockTestFixture")

    def test_names_an_empty_version_two_nunit_run(self):
        facts = self.collect(self.workspace(**{"test-results.xml": "<test-results name=\"mock\"/>"}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["nunit"])
        self.assertEqual(facts["totals"]["tests"], 0)

    def test_counts_a_namespaced_trx_run(self):
        facts = self.collect(self.workspace(**{"company.trx": TRX_RUN}))

        self.assertEqual(facts["totals"], {
            "tests": 3,
            "passed": 1,
            "failed": 1,
            "errors": 0,
            "skipped": 1,
            "durationMs": 113,
        })
        self.assertEqual(facts["failures"], [{
            "name": "DotnetTests.XUnitTests.CalculatorTests.Failing_Test",
            "classname": "DotnetTests.XUnitTests.CalculatorTests",
            "status": "failed",
            "file": None,
        }])

    def test_reads_a_trx_run_behind_a_byte_order_mark(self):
        facts = self.collect(self.workspace(**{"company.trx": "\ufeff" + TRX_RUN}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["trx"])
        self.assertEqual(facts["totals"]["tests"], 3)

    def test_counts_an_errored_trx_outcome_as_an_error(self):
        report = fixture("trx-errored.xml")

        facts = self.collect(self.workspace(**{"company.trx": report}))

        self.assertEqual(facts["totals"]["errors"], 2)
        self.assertEqual(facts["totals"]["failed"], 0)
        self.assertEqual(facts["totals"]["durationMs"], 61500)

    def test_counts_a_ctrf_report(self):
        facts = self.collect(self.workspace(**{"jest-ctrf.json": CTRF_RUN}))

        self.assertEqual(facts["totals"]["tests"], 3)
        self.assertEqual(facts["totals"]["failed"], 1)
        self.assertEqual(facts["totals"]["skipped"], 1)
        self.assertEqual(facts["totals"]["durationMs"], 2000)
        self.assertEqual(facts["failures"], [{
            "name": "reports a failed widget",
            "classname": "src/dashboard/Dashboard.test.tsx",
            "status": "failed",
            "file": "src/dashboard/Dashboard.test.tsx",
        }])

    def test_counts_an_unknown_ctrf_status_as_skipped(self):
        report = fixture("ctrf-unknown-status.json")

        facts = self.collect(self.workspace(**{"cypress-ctrf.json": report}))

        self.assertEqual(facts["totals"]["skipped"], 2)

    def test_counts_an_open_test_report_event_stream(self):
        facts = self.collect(self.workspace(**{"open-test-report.xml": OTR_EVENTS}))

        self.assertEqual(facts["totals"], {
            "tests": 4,
            "passed": 1,
            "failed": 1,
            "errors": 1,
            "skipped": 1,
            "durationMs": 175,
        })
        self.assertEqual(
            [(case["name"], case["classname"], case["status"]) for case in facts["failures"] + facts["skipped"]],
            [
                ("dividesByZero()", "com.example.CalculatorTests", "failed"),
                ("readsConfiguration()", "com.example.CalculatorTests", "error"),
                ("usesGpu()", "com.example.CalculatorTests", "skipped"),
            ],
        )

    def test_reads_an_open_test_report_hierarchy(self):
        report = fixture("otr-hierarchy.xml")

        facts = self.collect(self.workspace(**{"open-test-report.xml": report}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["otr"])
        self.assertEqual(facts["totals"]["tests"], 3)
        self.assertEqual(facts["totals"]["failed"], 1)
        self.assertEqual(facts["totals"]["skipped"], 1)
        self.assertEqual(facts["totals"]["durationMs"], 550)
        self.assertEqual(
            [(case["name"], case["classname"]) for case in facts["failures"] + facts["skipped"]],
            [("dividesByZero()", "com.example.CalculatorTests"), ("convertsCelsius()", "com.example.CalculatorTests")],
        )

    def test_names_an_empty_open_test_report_hierarchy(self):
        report = """<h:execution xmlns:h="https://schemas.opentest4j.org/reporting/hierarchy/0.2.0"/>"""

        facts = self.collect(self.workspace(**{"open-test-report.xml": report}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["otr"])

    def test_reads_no_tests_from_a_coverage_report(self):
        for text in COVERAGE_REPORTS:
            facts = self.collect(self.workspace(**{"junit.xml": text, "coverage-ctrf.json": text}))

            self.assertEqual(facts["source"], "none", text)

    def test_reads_nothing_from_malformed_input(self):
        for text in MALFORMED:
            facts = self.collect(self.workspace(**{"junit.xml": text, "broken-ctrf.json": text}))

            self.assertEqual(facts["source"], "none", text)


if __name__ == "__main__":
    unittest.main()
