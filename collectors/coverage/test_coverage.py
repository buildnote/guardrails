#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

JACOCO = fixture("jacoco.xml")

JACOCO_BROKER = fixture("jacoco-broker.xml")

COBERTURA = fixture("cobertura.xml")

LCOV = fixture("lcov.info")

ISTANBUL = fixture("istanbul.json")

JACOCO_CORE = fixture("jacoco-core.xml")

LCOV_TRACEFILE = fixture("lcov-tracefile.info")

COBERTURA_PACKAGES = fixture("cobertura-packages.xml")

ISTANBUL_FILES = fixture("istanbul-files.json")

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

TEST_REPORTS = (
    """<testsuite name="units"><testcase name="a" time="0.25"/></testsuite>""",
    """<test-run id="2" duration="1.5"><test-case id="1" name="Adds" result="Passed"/></test-run>""",
    """<TestRun id="1"><Results><UnitTestResult testId="a" testName="Adds" outcome="Passed"/></Results></TestRun>""",
    """{"results": {"tests": [{"name": "adds", "status": "passed", "duration": 1}]}}""",
    """<events><started id="1" name="adds" time="2026-08-20T09:15:00.100Z"/></events>""",
)


def jacoco_with(count):
    sources = "".join(
        """<sourcefile name="Widget%02d.kt"><line nr="1" mi="0" ci="1"/>%s</sourcefile>""" % (
            number,
            "".join(
                """<line nr="%d" mi="1" ci="0"/>""" % (line + 2) for line in range(number + 1)
            ),
        )
        for number in range(count)
    )
    bulk = """<sourcefile name="Bulk.kt">%s%s</sourcefile>""" % (
        "".join("""<line nr="%d" mi="0" ci="1"/>""" % (line + 1) for line in range(40)),
        "".join("""<line nr="%d" mi="1" ci="0"/>""" % (line + 41) for line in range(5)),
    )

    return """<report name="widget"><package name="com/company">%s%s</package></report>""" % (sources, bulk)


class CoverageTest(CollectorTestCase):
    COLLECTOR = "coverage"

    def test_reads_a_jacoco_report(self):
        facts = self.collect(self.workspace(**{"jacocoTestReport.xml": JACOCO}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["lines"], {"covered": 3, "missed": 1, "percent": 75.0})
        self.assertEqual(facts["branches"], {"covered": 1, "missed": 3, "percent": 25.0})
        self.assertEqual(facts["files"], 1)
        self.assertEqual(
            facts["byFile"],
            {"com/company/widget/Queue.kt": {"covered": 3, "missed": 1, "percent": 75.0}},
        )
        self.assertEqual(facts["dropped"], 0)

    def test_names_every_report_it_read(self):
        facts = self.collect(self.workspace(**{"jacocoTestReport.xml": JACOCO}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "jacocoTestReport.xml")
        self.assertEqual(report["format"], "jacoco")
        self.assertIsNotNone(report["modified"])

    def test_reads_a_cobertura_report(self):
        facts = self.collect(self.workspace(**{"cobertura-coverage.xml": COBERTURA}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["cobertura"])
        self.assertEqual(facts["lines"], {"covered": 1, "missed": 1, "percent": 50.0})
        self.assertEqual(facts["branches"], {"covered": 3, "missed": 1, "percent": 75.0})
        self.assertEqual(facts["byFile"]["src/app.py"]["percent"], 50.0)

    def test_reads_an_lcov_report(self):
        facts = self.collect(self.workspace(**{"lcov.info": LCOV}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["lcov"])
        self.assertEqual(facts["lines"], {"covered": 2, "missed": 1, "percent": 66.67})
        self.assertEqual(facts["byFile"]["src/app.js"], {"covered": 2, "missed": 1, "percent": 66.67})

    def test_leaves_the_branches_null_when_the_format_carries_none(self):
        facts = self.collect(self.workspace(**{"lcov.info": LCOV}))

        self.assertIsNone(facts["branches"])

    def test_reads_an_istanbul_report(self):
        facts = self.collect(self.workspace(**{"coverage-final.json": ISTANBUL}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["istanbul"])
        self.assertEqual(facts["lines"], {"covered": 1, "missed": 1, "percent": 50.0})
        self.assertEqual(facts["branches"]["covered"], 1)
        self.assertEqual(facts["byFile"]["src/widget.ts"]["missed"], 1)

    def test_merges_every_report_into_one_total(self):
        facts = self.collect(self.workspace(**{
            "jacocoTestReport.xml": JACOCO,
            "jacoco-broker.xml": JACOCO_BROKER,
            "lcov.info": LCOV,
        }))

        self.assertEqual(len(facts["reports"]), 3)
        self.assertEqual(facts["files"], 3)
        self.assertEqual(facts["lines"], {"covered": 6, "missed": 3, "percent": 66.67})

    def test_collects_a_report_that_measured_nothing(self):
        facts = self.collect(self.workspace(**{"jacocoTestReport.xml": "<report name=\"widget\"/>"}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["lines"], {"covered": 0, "missed": 0, "percent": 0.0})
        self.assertEqual(facts["files"], 0)
        self.assertEqual(facts["byFile"], {})

    def test_drops_files_over_the_limit_most_uncovered_lines_first(self):
        facts = self.collect(self.workspace(**{"jacocoTestReport.xml": jacoco_with(6)}), maxFiles="3")

        self.assertEqual(facts["files"], 7)
        self.assertEqual(facts["lines"], {"covered": 46, "missed": 26, "percent": 63.89})
        self.assertEqual(
            list(facts["byFile"]),
            ["com/company/Widget05.kt", "com/company/Bulk.kt", "com/company/Widget04.kt"],
        )
        self.assertEqual(facts["byFile"]["com/company/Bulk.kt"], {"covered": 40, "missed": 5, "percent": 88.89})
        self.assertEqual(facts["dropped"], 4)

    def test_carries_no_line_numbers_unless_it_is_asked(self):
        facts = self.collect(self.workspace(**{"jacocoTestReport.xml": JACOCO}))

        self.assertEqual(
            sorted(facts["byFile"]["com/company/widget/Queue.kt"]),
            ["covered", "missed", "percent"],
        )

    def test_carries_the_line_numbers_when_it_is_asked(self):
        facts = self.collect(self.workspace(**{"jacocoTestReport.xml": JACOCO}), lineDetail="true")
        entry = facts["byFile"]["com/company/widget/Queue.kt"]

        self.assertEqual(entry["coveredLines"], [5, 6, 9])
        self.assertEqual(entry["missedLines"], [14])
        self.assertEqual(entry["covered"], 3)

    def test_ignores_a_report_it_cannot_read(self):
        facts = self.collect(self.workspace(**{
            "coverage-broken.xml": "<coverage line-rate=\"0.5\">",
            "jacocoTestReport.xml": JACOCO,
        }))

        self.assertEqual([report["path"] for report in facts["reports"]], ["jacocoTestReport.xml"])
        self.assertEqual(facts["lines"]["covered"], 3)

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no coverage report matched", facts["reason"])
        self.assertIn("lcov.info", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"jacocoTestReport.xml": JACOCO, "lcov.info": LCOV})

        facts = self.collect(workspace, reports="lcov.info")

        self.assertEqual([report["format"] for report in facts["reports"]], ["lcov"])
        self.assertEqual(facts["files"], 1)

    def test_names_the_format_of_every_report(self):
        facts = self.collect(self.workspace(**{
            "jacoco.xml": JACOCO_CORE,
            "lcov.info": LCOV_TRACEFILE,
            "cobertura.xml": COBERTURA_PACKAGES,
            "coverage-final.json": ISTANBUL_FILES,
        }))

        self.assertEqual(
            [(report["path"], report["format"]) for report in facts["reports"]],
            [
                ("cobertura.xml", "cobertura"),
                ("coverage-final.json", "istanbul"),
                ("jacoco.xml", "jacoco"),
                ("lcov.info", "lcov"),
            ],
        )
        self.assertEqual(facts["files"], 8)

    def test_reads_the_lines_of_every_jacoco_source_file(self):
        facts = self.collect(self.workspace(**{"jacoco.xml": JACOCO_CORE}), lineDetail="true")

        self.assertEqual(facts["byFile"], {
            "io/buildnote/core/Calculator.kt": {
                "covered": 2, "missed": 1, "percent": 66.67, "coveredLines": [7, 8], "missedLines": [11],
            },
            "io/buildnote/core/Formatter.kt": {
                "covered": 1, "missed": 1, "percent": 50.0, "coveredLines": [4], "missedLines": [5],
            },
        })
        self.assertEqual(facts["lines"], {"covered": 3, "missed": 2, "percent": 60.0})
        self.assertEqual(facts["branches"], {"covered": 1, "missed": 1, "percent": 50.0})

    def test_falls_back_to_the_jacoco_class_counters(self):
        report = fixture("jacoco-class-counters.xml")

        facts = self.collect(self.workspace(**{"jacoco.xml": report}))

        self.assertEqual(facts["files"], 0)
        self.assertEqual(facts["lines"], {"covered": 3, "missed": 1, "percent": 75.0})
        self.assertEqual(facts["branches"], {"covered": 2, "missed": 2, "percent": 50.0})

    def test_survives_an_unreadable_jacoco_counter(self):
        report = fixture("jacoco-unreadable-counter.xml")

        facts = self.collect(self.workspace(**{"jacoco.xml": report}), lineDetail="true")

        self.assertEqual(facts["byFile"], {
            "io/buildnote/core/Calculator.kt": {
                "covered": 0, "missed": 1, "percent": 0.0, "coveredLines": [], "missedLines": [7],
            },
        })

    def test_reads_the_lines_of_every_lcov_record(self):
        facts = self.collect(self.workspace(**{"lcov.info": LCOV_TRACEFILE}), lineDetail="true")

        self.assertEqual(
            dict((path, (entry["coveredLines"], entry["missedLines"])) for path, entry in facts["byFile"].items()),
            {"src/app/calculator.ts": ([3, 4, 8], [7]), "src/app/format.ts": ([1], [2])},
        )
        self.assertEqual(facts["lines"], {"covered": 4, "missed": 2, "percent": 66.67})
        self.assertEqual(facts["branches"], {"covered": 1, "missed": 1, "percent": 50.0})

    def test_merges_repeated_lcov_records_for_one_file(self):
        report = "SF:src/app.ts\nDA:1,1\nend_of_record\nSF:src/app.ts\nDA:2,0\nend_of_record\n"

        facts = self.collect(self.workspace(**{"lcov.info": report}), lineDetail="true")

        self.assertEqual(facts["files"], 1)
        self.assertEqual(facts["byFile"]["src/app.ts"]["coveredLines"], [1])
        self.assertEqual(facts["byFile"]["src/app.ts"]["missedLines"], [2])

    def test_prefers_a_covering_lcov_record_over_a_missing_one(self):
        report = "SF:src/app.ts\nDA:1,0\nend_of_record\nSF:src/app.ts\nDA:1,4\nend_of_record\n"

        facts = self.collect(self.workspace(**{"lcov.info": report}), lineDetail="true")

        self.assertEqual(facts["byFile"]["src/app.ts"]["coveredLines"], [1])
        self.assertEqual(facts["byFile"]["src/app.ts"]["missedLines"], [])

    def test_uses_the_lcov_record_branch_totals_when_there_are_no_branch_entries(self):
        report = "SF:src/app.ts\nDA:1,1\nBRF:4\nBRH:3\nend_of_record\n"

        facts = self.collect(self.workspace(**{"lcov.info": report}))

        self.assertEqual(facts["branches"], {"covered": 3, "missed": 1, "percent": 75.0})

    def test_reports_nothing_covered_as_zero_percent(self):
        report = "SF:src/app.ts\nLF:0\nLH:0\nend_of_record\n"

        facts = self.collect(self.workspace(**{"lcov.info": report}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["lines"], {"covered": 0, "missed": 0, "percent": 0.0})

    def test_uses_the_lcov_record_totals_when_there_are_no_line_entries(self):
        report = "SF:src/app.ts\nLF:10\nLH:4\nend_of_record\n"

        facts = self.collect(self.workspace(**{"lcov.info": report}))

        self.assertEqual(facts["files"], 0)
        self.assertEqual(facts["lines"], {"covered": 4, "missed": 6, "percent": 40.0})

    def test_rejects_a_log_that_merely_mentions_a_source_file(self):
        facts = self.collect(self.workspace(**{"lcov.info": "compiling SF:src/app.ts\ndone\n"}))

        self.assertEqual(facts["source"], "none")

    def test_reads_the_lines_of_every_cobertura_class(self):
        facts = self.collect(self.workspace(**{"cobertura.xml": COBERTURA_PACKAGES}), lineDetail="true")

        self.assertEqual(
            dict((path, (entry["coveredLines"], entry["missedLines"])) for path, entry in facts["byFile"].items()),
            {"app/calculator.py": ([1, 4], [7, 8]), "app/format.py": ([1, 2], [])},
        )
        self.assertEqual(facts["lines"], {"covered": 4, "missed": 2, "percent": 66.67})
        self.assertEqual(facts["branches"], {"covered": 1, "missed": 1, "percent": 50.0})

    def test_merges_cobertura_classes_that_share_a_filename(self):
        report = fixture("cobertura-shared-filename.xml")

        facts = self.collect(self.workspace(**{"cobertura.xml": report}), lineDetail="true")

        self.assertEqual(facts["files"], 1)
        self.assertEqual(facts["byFile"]["app/outer.py"]["coveredLines"], [1])
        self.assertEqual(facts["byFile"]["app/outer.py"]["missedLines"], [5])

    def test_reports_no_cobertura_branches_when_none_were_recorded(self):
        report = fixture("cobertura-no-branches.xml")

        facts = self.collect(self.workspace(**{"cobertura.xml": report}))

        self.assertIsNone(facts["branches"])

    def test_reads_the_statements_of_every_istanbul_file(self):
        facts = self.collect(self.workspace(**{"coverage-final.json": ISTANBUL_FILES}), lineDetail="true")

        self.assertEqual(
            dict((path, (entry["coveredLines"], entry["missedLines"])) for path, entry in facts["byFile"].items()),
            {"/repo/src/calculator.js": ([3, 7], [11]), "/repo/src/format.js": ([1, 2], [])},
        )
        self.assertEqual(facts["lines"], {"covered": 4, "missed": 1, "percent": 80.0})
        self.assertEqual(facts["branches"], {"covered": 1, "missed": 1, "percent": 50.0})

    def test_reports_no_istanbul_branches_when_none_were_recorded(self):
        report = fixture("istanbul-no-branches.json")

        facts = self.collect(self.workspace(**{"coverage-final.json": report}))

        self.assertIsNone(facts["branches"])

    def test_reads_no_coverage_from_a_test_report(self):
        for text in TEST_REPORTS:
            facts = self.collect(self.workspace(**{"coverage.xml": text, "coverage-final.json": text}))

            self.assertEqual(facts["source"], "none", text)

    def test_reads_nothing_from_malformed_input(self):
        for text in MALFORMED:
            facts = self.collect(self.workspace(**{
                "coverage.xml": text,
                "coverage-final.json": text,
                "lcov.info": text,
            }))

            self.assertEqual(facts["source"], "none", text)


if __name__ == "__main__":
    unittest.main()
