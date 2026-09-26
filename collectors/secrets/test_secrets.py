#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

SECRET = "the-secret-value-that-must-never-be-collected"

GITLEAKS_VERSION = "gitleaks version 8.18.4"

TRUFFLEHOG_VERSION = "trufflehog 3.63.2"

SARIF = fixture("gitleaks.sarif")

LEAKY_SARIF = fixture("leaky-gitleaks.sarif") % {"secret": SECRET}

def json_lines(*findings):
    return "".join(json.dumps(finding) + "\n" for finding in findings)


TRUFFLEHOG = json_lines(
    {
        "SourceMetadata": {"Data": {"Filesystem": {"file": "config/app.yaml", "line": 12}}},
        "DetectorName": "AWS",
        "DecoderName": "PLAIN",
        "Verified": True,
        "Raw": SECRET,
        "RawV2": SECRET,
        "Redacted": SECRET,
    },
    {
        "SourceMetadata": {"Data": {"Filesystem": {"file": "deploy/values.yaml", "line": 3}}},
        "DetectorName": "SlackWebhook",
        "DecoderName": "PLAIN",
        "Verified": False,
        "Raw": SECRET,
    },
)

BASELINE = fixture("baseline.json")


def gitleaks_json(count):
    return json.dumps([
        {
            "RuleID": "generic-api-key",
            "Description": "Detected a generic API key",
            "File": "config/service-%d.yaml" % number,
            "StartLine": number + 1,
            "Secret": SECRET,
            "Match": "apiKey: %s" % SECRET,
            "Message": "chore: add %s" % SECRET,
            "Author": "Dana",
            "Email": "dana@example.com",
        }
        for number in range(count)
    ])


class SecretsTest(CollectorTestCase):
    COLLECTOR = "secrets"

    def gitleaks(self, stdout=SARIF, code=1, version=GITLEAKS_VERSION):
        return self.shim("gitleaks", version=version, responses=[["detect", stdout, "", code]])

    def trufflehog(self, stdout=TRUFFLEHOG, code=0):
        return self.shim("trufflehog", version=TRUFFLEHOG_VERSION, responses=[["--json", stdout, "", code]])

    def test_reads_a_gitleaks_sarif_report(self):
        facts = self.collect(self.workspace(**{"gitleaks.sarif": SARIF}))
        finding = facts["findings"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["counts"]["total"], 1)
        self.assertEqual(facts["counts"]["bySeverity"]["high"], 1)
        self.assertEqual(facts["counts"]["bySeverity"]["critical"], 0)
        self.assertEqual(finding["id"], "aws-access-token")
        self.assertEqual(finding["severity"], "high")
        self.assertIn("has detected a secret", finding["message"])
        self.assertEqual(finding["path"], "config/app.yaml")
        self.assertEqual(finding["line"], 12)
        self.assertEqual(len(finding["fingerprint"]), 16)
        self.assertEqual(facts["dropped"], 0)

    def test_names_the_report_it_read(self):
        facts = self.collect(self.workspace(**{"gitleaks.sarif": SARIF}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "gitleaks.sarif")
        self.assertEqual(report["format"], "sarif")
        self.assertIsNotNone(report["modified"])

    def test_prefers_the_report_the_build_already_produced_over_the_tool(self):
        self.gitleaks()

        facts = self.collect(self.workspace(**{"gitleaks.sarif": SARIF}))

        self.assertEqual(facts["source"], "report")
        self.assertNotIn("tool", facts)

    def test_reads_a_gitleaks_json_report(self):
        facts = self.collect(self.workspace(**{"gitleaks.json": gitleaks_json(2)}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["gitleaks"])
        self.assertEqual(facts["counts"]["total"], 2)
        self.assertEqual(facts["findings"][0]["id"], "generic-api-key")
        self.assertEqual(facts["findings"][0]["path"], "config/service-0.yaml")
        self.assertEqual(facts["findings"][0]["line"], 1)

    def test_reads_a_trufflehog_report_and_rates_a_verified_secret_critical(self):
        facts = self.collect(self.workspace(**{"trufflehog.json": TRUFFLEHOG}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["trufflehog"])
        self.assertEqual(facts["counts"]["bySeverity"]["critical"], 1)
        self.assertEqual(facts["counts"]["bySeverity"]["high"], 1)
        self.assertEqual(facts["findings"][0]["id"], "AWS")
        self.assertEqual(facts["findings"][0]["path"], "config/app.yaml")
        self.assertEqual(facts["findings"][0]["line"], 12)

    def test_reads_a_detect_secrets_baseline(self):
        facts = self.collect(self.workspace(**{".secrets.baseline": BASELINE}))

        self.assertEqual([report["format"] for report in facts["reports"]], ["detect-secrets"])
        self.assertEqual(facts["findings"][0]["id"], "AWS Access Key")
        self.assertEqual(facts["findings"][0]["line"], 12)

    def test_runs_gitleaks_when_no_report_is_there(self):
        path = self.gitleaks()

        facts = self.collect(self.workspace())

        self.assertEqual(facts["source"], "tool")
        self.assertEqual(facts["reports"], [])
        self.assertEqual(facts["tool"]["name"], "gitleaks")
        self.assertEqual(facts["tool"]["version"], "8.18.4")
        self.assertEqual(facts["tool"]["path"], path)
        self.assertEqual(facts["tool"]["args"][0], "detect")
        self.assertEqual(facts["tool"]["exitCode"], 1)
        self.assertGreaterEqual(facts["tool"]["durationMs"], 0)
        self.assertEqual(facts["counts"]["total"], 1)
        self.assertEqual(facts["findings"][0]["id"], "aws-access-token")

    def test_treats_a_clean_scan_as_a_result_rather_than_an_absence(self):
        self.gitleaks(stdout="""{"version": "2.1.0", "runs": []}""", code=0)

        facts = self.collect(self.workspace())

        self.assertEqual(facts["source"], "tool")
        self.assertEqual(facts["tool"]["exitCode"], 0)
        self.assertEqual(facts["counts"]["total"], 0)
        self.assertEqual(facts["findings"], [])

    def test_scans_the_working_tree_unless_the_history_is_asked_for(self):
        self.gitleaks()

        tree = self.collect(self.workspace())
        history = self.collect(self.workspace(), scanHistory="true")

        self.assertIn("--no-git", tree["tool"]["args"])
        self.assertNotIn("--no-git", history["tool"]["args"])
        self.assertIn("--redact", history["tool"]["args"])

    def test_falls_back_to_trufflehog_when_gitleaks_is_not_on_the_runner(self):
        self.trufflehog()

        facts = self.collect(self.workspace())

        self.assertEqual(facts["tool"]["name"], "trufflehog")
        self.assertEqual(facts["tool"]["version"], "3.63.2")
        self.assertEqual(facts["tool"]["args"], ["filesystem", ".", "--json", "--no-update"])
        self.assertEqual(facts["counts"]["total"], 2)

        history = self.collect(self.workspace(), scanHistory="true")

        self.assertEqual(history["tool"]["args"], ["git", "file://.", "--json", "--no-update"])

    def test_says_what_to_install_when_there_is_neither_a_report_nor_a_tool(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no readable secret report matched", facts["reason"])
        self.assertIn("gitleaks*.sarif", facts["reason"])
        self.assertIn("gitleaks", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_does_not_read_a_tool_that_printed_garbage_as_a_clean_scan(self):
        self.gitleaks(stdout="Error: unknown flag --redact\n", code=2)

        facts = self.collect(self.workspace())

        self.assertEqual(facts["source"], "none")
        self.assertIn("gitleaks exited with 2", facts["reason"])
        self.assertEqual(facts["tool"]["exitCode"], 2)
        self.assertNotIn("findings", facts)

    def test_ignores_a_report_it_cannot_read(self):
        workspace = self.workspace(**{"gitleaks-broken.json": "{ not json", "gitleaks.sarif": SARIF})

        facts = self.collect(workspace)

        self.assertEqual([report["path"] for report in facts["reports"]], ["gitleaks.sarif"])

    def test_never_carries_the_matched_secret_into_the_facts(self):
        workspace = self.workspace(**{
            "gitleaks.sarif": LEAKY_SARIF,
            "gitleaks.json": gitleaks_json(1),
            "trufflehog.json": TRUFFLEHOG,
        })

        facts = self.collect(workspace)

        self.assertEqual(facts["counts"]["total"], 4)
        self.assertNotIn(SECRET, json.dumps(facts))

    def test_drops_findings_over_the_limit_but_keeps_the_counts_whole(self):
        facts = self.collect(self.workspace(**{"gitleaks.json": gitleaks_json(12)}), maxFindings="5")

        self.assertEqual(facts["counts"]["total"], 12)
        self.assertEqual(len(facts["findings"]), 5)
        self.assertEqual(facts["dropped"], 7)

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"gitleaks.sarif": SARIF, "trufflehog.json": TRUFFLEHOG})

        facts = self.collect(workspace, reports="trufflehog*.json")

        self.assertEqual([report["format"] for report in facts["reports"]], ["trufflehog"])


if __name__ == "__main__":
    unittest.main()
