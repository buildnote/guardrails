#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

SECRET = "s3cr3t-value-that-must-never-leave-the-collector"

GITLEAKS_VERSION = "gitleaks version 8.18.4"

UNSCANNED = {"README.md": "widget\n"}


def sarif(*results):
    return """{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "gitleaks", "semanticVersion": "v8.18.4"}},
      "results": [%s]}]}""" % ",".join(results)


def found(rule, level, path, line, message=None):
    return """{"ruleId": "%s", "level": "%s", "message": {"text": "%s"},
      "locations": [{"physicalLocation": {"artifactLocation": {"uri": "%s"},
      "region": {"startLine": %d}}}]}""" % (
        rule, level, message or "%s has detected a secret" % rule, path, line
    )


VERIFIED = json.dumps({
    "SourceMetadata": {"Data": {"Filesystem": {"file": "deploy/values.yaml", "line": 3}}},
    "DetectorName": "AWS",
    "Verified": True,
    "Raw": SECRET,
}) + "\n"


class NoHardcodedCredentialsTest(GuardrailTestCase):
    SCRIPT = "no-hardcoded-credentials.py"
    COLLECT = ["secrets"]

    def gitleaks(self, stdout, code=1):
        return self.shim("gitleaks", version=GITLEAKS_VERSION, responses=[["detect", stdout, "", code]])

    def test_passes_a_checkout_the_detector_reported_clean(self):
        self.assert_passed(self.check(self.workspace(**{"gitleaks.sarif": sarif()})))

    def test_fails_a_credential_at_the_gate(self):
        report = sarif(found("aws-access-token", "error", "config/app.yaml", 12))

        violation = self.assert_violation(
            self.check(self.workspace(**{"gitleaks.sarif": report})),
            "high severity credential matching aws-access-token is in the checkout at config/app.yaml:12",
        )

        self.assertEqual(violation["evidence"], "config/app.yaml:12 aws-access-token")

    def test_fails_a_credential_the_detector_verified_against_the_service(self):
        self.assert_violation(
            self.check(self.workspace(**{"trufflehog.json": VERIFIED})),
            "critical severity credential matching AWS is in the checkout at deploy/values.yaml:3",
        )

    def test_passes_a_credential_below_the_gate(self):
        report = sarif(found("low.confidence.rule", "warning", "config/app.yaml", 12))

        self.assert_passed(self.check(self.workspace(**{"gitleaks.sarif": report})))

    def test_gates_at_the_severity_it_is_given(self):
        report = sarif(found("low.confidence.rule", "warning", "config/app.yaml", 12))
        workspace = self.workspace(**{"gitleaks.sarif": report})

        self.assert_passed(self.check(workspace))
        self.assertEqual(self.check(workspace, severity="medium").code, 1)

    def test_leaves_out_a_rule_the_team_has_accepted(self):
        report = sarif(found("generic-api-key", "error", "test/fixture.yaml", 4))
        workspace = self.workspace(**{"gitleaks.sarif": report})

        self.assertEqual(self.check(workspace).code, 1)
        self.assert_passed(self.check(workspace, ignore="generic-api-key"))

    def test_leaves_out_only_the_rules_it_is_given(self):
        report = sarif(
            found("generic-api-key", "error", "test/fixture.yaml", 4),
            found("aws-access-token", "error", "config/app.yaml", 12),
        )

        self.assert_violation(
            self.check(self.workspace(**{"gitleaks.sarif": report}), ignore="generic-api-key, unused-rule"),
            "aws-access-token",
        )

    def test_reports_every_credential_at_the_gate(self):
        report = sarif(
            found("aws-access-token", "error", "config/one.yaml", 1),
            found("slack-webhook", "error", "config/two.yaml", 2),
        )

        self.assertEqual(len(self.check(self.workspace(**{"gitleaks.sarif": report})).violations), 2)

    def test_gates_a_credential_the_collector_found_by_running_the_detector(self):
        self.gitleaks(sarif(found("aws-access-token", "error", "config/app.yaml", 12)))

        self.assert_violation(
            self.check(self.workspace(**UNSCANNED)),
            "high severity credential matching aws-access-token",
        )

    def test_skips_when_nothing_scanned_the_checkout(self):
        self.assert_skipped(
            self.check(self.workspace(**UNSCANNED)),
            "no readable secret report matched",
        )

    def test_skips_when_the_detector_printed_nothing_it_could_read(self):
        self.gitleaks("Error: unknown flag --redact\n", code=2)

        self.assert_skipped(self.check(self.workspace(**UNSCANNED)), "gitleaks exited with 2")

    def test_skips_where_the_detector_ran_guardrail_violates(self):
        workspace = self.workspace(**UNSCANNED)

        self.assert_skipped(self.check(workspace), "no readable secret report matched")

        self.SCRIPT = "detector-ran.py"

        self.assert_violation(self.check(workspace), "Nothing looked for a credential in this checkout")

    def test_skips_a_severity_nobody_recognises(self):
        report = sarif(found("aws-access-token", "error", "config/app.yaml", 12))

        self.assert_skipped(
            self.check(self.workspace(**{"gitleaks.sarif": report}), severity="catastrophic"),
            "severity 'catastrophic' is not one of",
        )

    def test_never_carries_the_matched_secret_into_its_output(self):
        report = sarif(found("generic-api-key", "error", "config/app.yaml", 12, message=SECRET))
        workspace = self.workspace(**{"gitleaks.sarif": report})

        facts = self.collected(workspace, ["secrets"], {})
        result = self.check(workspace)

        self.assertIn(SECRET, json.dumps(facts))
        self.assertEqual(result.code, 1)
        self.assertNotIn(SECRET, json.dumps(result.payload))


if __name__ == "__main__":
    unittest.main()
