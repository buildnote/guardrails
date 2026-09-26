#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

FINDING_KEYS = ["fingerprint", "fixedIn", "id", "identifiers", "kind", "line", "message", "package", "path", "severity"]

MALFORMED = [
    "",
    "   ",
    "not json at all",
    "{",
    "{\"runs\": ",
    "[1, 2, 3]",
    "null",
    "{\"unexpected\": true}",
    "<bom>",
    "\x00\x01",
]

SARIF = fixture("semgrep-oss.sarif")

TRIVY = fixture("trivy-log4j.json")

GRYPE = fixture("grype.json")


def trivy_with(count):
    vulnerabilities = ",".join(
        """{"VulnerabilityID": "CVE-2024-%04d", "PkgName": "widget", "InstalledVersion": "1.0.0",
            "Severity": "LOW", "Title": "widget flaw %d"}""" % (number, number)
        for number in range(count)
    )

    return """{"SchemaVersion": 2, "Results": [{"Target": "go.sum", "Vulnerabilities": [%s]}]}""" % vulnerabilities


def sarif_document(runs):
    return json.dumps({
        "version": "2.1.0",
        "runs": [{"tool": {"driver": driver}, "results": results} for driver, results in runs],
    })


def result(rule="R1", level="error", text="m", **fields):
    found = {"ruleId": rule, "message": {"text": text}}
    if level is not None:
        found["level"] = level
    found.update(fields)

    return found


def located(line, uri="src/app.py"):
    return [{"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": line}}}]


class ScanTest(CollectorTestCase):
    COLLECTOR = "scan"

    def test_reads_a_sarif_report(self):
        facts = self.collect(self.workspace(**{"semgrep.sarif": SARIF}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["counts"]["total"], 1)
        self.assertEqual(facts["counts"]["high"], 1)
        self.assertEqual(facts["kinds"]["sast"], 1)
        self.assertEqual(facts["findings"][0]["path"], "service/src/main/kotlin/Queue.kt")
        self.assertEqual(facts["findings"][0]["line"], 12)
        self.assertEqual(facts["dropped"], 0)

    def test_names_the_scanner_that_wrote_the_report(self):
        facts = self.collect(self.workspace(**{"semgrep.sarif": SARIF}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "semgrep.sarif")
        self.assertEqual(report["format"], "sarif")
        self.assertEqual(report["producer"]["name"], "Semgrep OSS")
        self.assertEqual(report["producer"]["version"], "1.86.0")
        self.assertEqual(report["findings"], 1)
        self.assertIsNotNone(report["modified"])

    def test_reads_a_dependency_report(self):
        facts = self.collect(self.workspace(**{"trivy.json": TRIVY}))
        finding = facts["findings"][0]

        self.assertEqual(facts["counts"]["critical"], 1)
        self.assertEqual(facts["kinds"]["sca"], 1)
        self.assertEqual(finding["package"]["name"], "org.apache.logging.log4j:log4j-core")
        self.assertEqual(finding["package"]["version"], "2.14.1")
        self.assertEqual(finding["fixedIn"], "2.15.0")
        self.assertEqual(finding["identifiers"], ["CVE-2021-44228"])
        self.assertEqual(finding["severity"], "critical")

    def test_reads_every_report_it_finds(self):
        facts = self.collect(self.workspace(**{"semgrep.sarif": SARIF, "trivy.json": TRIVY}))

        self.assertEqual(len(facts["reports"]), 2)
        self.assertEqual(facts["counts"]["total"], 2)

    def test_gives_a_finding_a_fingerprint_that_survives_a_rerun(self):
        first = self.collect(self.workspace(**{"semgrep.sarif": SARIF}))
        second = self.collect(self.workspace(**{"semgrep.sarif": SARIF}))

        self.assertEqual(
            first["findings"][0]["fingerprint"],
            second["findings"][0]["fingerprint"],
        )

    def test_drops_findings_over_the_limit_but_keeps_the_counts_whole(self):
        facts = self.collect(self.workspace(**{"trivy.json": trivy_with(12)}), maxFindings="5")

        self.assertEqual(facts["counts"]["total"], 12)
        self.assertEqual(len(facts["findings"]), 5)
        self.assertEqual(facts["dropped"], 7)

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no scanner report matched", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"semgrep.sarif": SARIF, "trivy.json": TRIVY})

        facts = self.collect(workspace, reports="trivy*.json")

        self.assertEqual([report["format"] for report in facts["reports"]], ["trivy"])

    def test_ignores_a_report_it_cannot_read(self):
        facts = self.collect(self.workspace(**{"broken.sarif": "{ not json", "trivy.json": TRIVY}))

        self.assertEqual([report["path"] for report in facts["reports"]], ["trivy.json"])

    def test_ignores_an_sbom_that_is_not_a_findings_report(self):
        sbom = """{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}"""
        facts = self.collect(self.workspace(**{"cyclonedx.sarif": sbom}))

        self.assertEqual(facts["source"], "none")

    def findings_of(self, name, text=None, **inputs):
        return self.collect(self.workspace(**{name: fixture(name) if text is None else text}), **inputs)["findings"]

    def sarif_findings(self, *runs):
        return self.collect(self.workspace(**{"report.sarif": sarif_document(runs)}))["findings"]

    def test_names_the_tool_that_produced_a_sarif_report(self):
        report = self.collect(self.workspace(**{"semgrep.sarif": fixture("semgrep.sarif")}))["reports"][0]

        self.assertEqual(report["producer"], {"name": "Semgrep OSS", "version": "1.86.0"})

    def test_prefers_the_declared_version_over_the_semantic_one(self):
        report = self.collect(self.workspace(**{"codeql.sarif": fixture("codeql.sarif")}))["reports"][0]

        self.assertEqual(report["producer"], {"name": "CodeQL", "version": "2.19.3"})

    def test_reads_every_sarif_result_as_a_finding(self):
        findings = self.findings_of("semgrep.sarif")

        self.assertEqual(
            [(it["id"], it["severity"], it["path"], it["line"]) for it in findings],
            [
                ("python.lang.security.audit.subprocess-shell-true", "high", "tools/release.py", 42),
                ("javascript.express.security.audit.express-open-redirect", "medium", "server/routes.js", 118),
                ("generic.secrets.security.detected-generic-api-key", "low", "config/staging.env", 7),
            ],
        )

    def test_carries_the_message_and_the_kind_of_every_sarif_finding(self):
        findings = self.findings_of("semgrep.sarif")

        self.assertEqual(findings[0]["message"], "Detected subprocess function 'run' with shell=True")
        self.assertEqual([it["kind"] for it in findings], ["sast", "sast", "sast"])
        self.assertEqual([it["package"] for it in findings], [None, None, None])
        self.assertEqual([it["fixedIn"] for it in findings], [None, None, None])

    def test_a_security_severity_on_the_rule_beats_the_level_on_the_result(self):
        findings = self.findings_of("codeql.sarif")

        self.assertEqual(
            [(it["id"], it["severity"]) for it in findings],
            [
                ("java/sql-injection", "critical"),
                ("java/insecure-randomness", "medium"),
                ("java/unused-container", "low"),
            ],
        )

    def test_resolves_a_rule_the_result_names_by_index(self):
        finding = self.findings_of("codeql.sarif")[1]

        self.assertEqual(finding["id"], "java/insecure-randomness")
        self.assertEqual(finding["message"], "Random value is used in a security context.")

    def test_falls_back_to_the_level_the_rule_configures(self):
        self.assertEqual(self.findings_of("codeql.sarif")[2]["severity"], "low")

    def test_strips_a_file_uri_from_a_location(self):
        self.assertEqual(self.findings_of("codeql.sarif")[1]["path"], "/src/main/java/io/company/TokenFactory.java")

    def test_a_security_severity_on_the_result_beats_the_level(self):
        findings = self.sarif_findings(
            ({"name": "Trivy"}, [result("CVE-2021-44228", "note", properties={"security-severity": "10.0"})]),
        )

        self.assertEqual(findings[0]["severity"], "critical")

    def test_takes_the_identifiers_out_of_the_rule_and_the_message(self):
        findings = self.sarif_findings(
            ({"name": "Trivy"}, [result("CVE-2021-44228", text="log4j-core, see also GHSA-jfh8-c2jp-5v3q and CVE-2021-44228")]),
        )

        self.assertEqual(findings[0]["identifiers"], ["CVE-2021-44228", "GHSA-jfh8-c2jp-5v3q"])

    def test_a_finding_with_no_identifiers_carries_an_empty_list(self):
        self.assertEqual(self.findings_of("semgrep.sarif")[0]["identifiers"], [])

    def test_names_a_secret_scanner_by_its_driver(self):
        facts = self.collect(self.workspace(**{"gitleaks.sarif": fixture("gitleaks.sarif")}))

        self.assertEqual(facts["reports"][0]["producer"], {"name": "gitleaks", "version": "8.18.4"})
        self.assertEqual([it["kind"] for it in facts["findings"]], ["secret", "secret"])
        self.assertEqual([it["path"] for it in facts["findings"]], ["deploy/bootstrap.sh", "terraform/live/main/main.tf"])

    def test_infers_the_kind_from_the_driver(self):
        drivers = [
            ("gitleaks", "secret"),
            ("TruffleHog", "secret"),
            ("Checkov", "iac"),
            ("tfsec", "iac"),
            ("terrascan", "iac"),
            ("KICS", "iac"),
            ("Trivy", "sca"),
            ("grype", "sca"),
            ("Snyk Open Source", "sca"),
            ("Semgrep OSS", "sast"),
            ("Bandit", "sast"),
        ]

        findings = self.sarif_findings(*[({"name": name}, [result()]) for name, _ in drivers])

        self.assertEqual([it["kind"] for it in findings], [kind for _, kind in drivers])

    def test_reads_a_sarif_result_without_a_location(self):
        finding = self.sarif_findings(({"name": "Bandit"}, [result("B101", "warning")]))[0]

        self.assertIsNone(finding["path"])
        self.assertIsNone(finding["line"])

    def test_reads_a_region_whose_line_is_not_a_whole_number(self):
        lines = ["Infinity", "-Infinity", "NaN", '"twelve"', "true", "null", "{}"]
        results = ",".join(
            '{"ruleId":"R1","level":"error","message":{"text":"m"},"locations":[{"physicalLocation":'
            '{"artifactLocation":{"uri":"a.py"},"region":{"startLine":%s}}}]}' % line
            for line in lines
        )
        document = '{"runs":[{"tool":{"driver":{"name":"Semgrep"}},"results":[%s]}]}' % results

        findings = self.collect(self.workspace(**{"report.sarif": document}))["findings"]

        self.assertEqual([it["line"] for it in findings], [None] * len(lines))

    def test_fingerprints_a_path_that_is_not_valid_unicode(self):
        findings = self.sarif_findings(({"name": "Semgrep"}, [result(locations=located(1, "src/\ud800.py"))]))

        self.assertEqual(len(findings[0]["fingerprint"]), 16)

    def test_reads_a_sarif_report_that_found_nothing(self):
        facts = self.collect(self.workspace(**{"report.sarif": sarif_document([({"name": "Semgrep"}, [])])}))

        self.assertEqual(facts["findings"], [])
        self.assertEqual(facts["reports"][0]["producer"], {"name": "Semgrep", "version": None})

    def test_maps_every_sarif_level(self):
        findings = self.sarif_findings(({"name": "Semgrep"}, [
            result(level="error"),
            result(level="warning"),
            result(level="note"),
            result(level="none"),
            result(level="catastrophic"),
            result(level=None),
        ]))

        self.assertEqual([it["severity"] for it in findings], ["high", "medium", "low", "info", "unknown", "unknown"])

    def test_maps_a_security_severity_score(self):
        scores = [
            ("note", "9.0", "critical"),
            ("note", "10.0", "critical"),
            ("note", "8.9", "high"),
            ("note", "7.0", "high"),
            ("note", "6.9", "medium"),
            ("note", "4.0", "medium"),
            ("note", "3.9", "low"),
            ("note", "0.1", "low"),
            ("error", "0.0", "info"),
        ]

        findings = self.sarif_findings(({"name": "Semgrep"}, [
            result(level=level, properties={"security-severity": score}) for level, score, _ in scores
        ]))

        self.assertEqual([it["severity"] for it in findings], [severity for _, _, severity in scores])

    def test_ignores_a_security_severity_that_is_not_a_number(self):
        findings = self.sarif_findings(({"name": "Semgrep"}, [
            result(properties={"security-severity": score}) for score in ["critical", None, True]
        ]))

        self.assertEqual([it["severity"] for it in findings], ["high", "high", "high"])

    def test_maps_the_severities_the_scanners_name(self):
        named = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NEGLIGIBLE", "UNKNOWN", "MODERATE", "Critical", " negligible ",
                 "catastrophic", "", None, 7]
        vulnerabilities = [
            {"VulnerabilityID": "CVE-2024-%04d" % number, "PkgName": "widget", "Severity": severity}
            for number, severity in enumerate(named)
        ]
        report = json.dumps({"SchemaVersion": 2, "Results": [{"Target": "go.sum", "Vulnerabilities": vulnerabilities}]})

        findings = self.findings_of("trivy.json", report)

        self.assertEqual(
            [it["severity"] for it in findings],
            ["critical", "high", "medium", "low", "low", "unknown", "medium", "critical", "low",
             "unknown", "unknown", "unknown", "unknown"],
        )

    def test_names_trivy_as_the_producer(self):
        report = self.collect(self.workspace(**{"trivy.json": fixture("trivy.json")}))["reports"][0]

        self.assertEqual(report["format"], "trivy")
        self.assertEqual(report["producer"], {"name": "trivy", "version": None})

    def test_reads_every_class_of_trivy_result(self):
        findings = self.findings_of("trivy.json")

        self.assertEqual(
            [(it["id"], it["severity"], it["kind"]) for it in findings],
            [
                ("CVE-2024-4068", "high", "sca"),
                ("GHSA-3xgq-45jj-v275", "medium", "sca"),
                ("CVE-2023-5363", "critical", "sca"),
                ("DS002", "high", "iac"),
                ("aws-access-key-id", "critical", "secret"),
            ],
        )

    def test_reads_the_package_a_trivy_vulnerability_affects(self):
        finding = self.findings_of("trivy.json")[0]

        self.assertEqual(finding["package"], {"name": "braces", "version": "3.0.2"})
        self.assertEqual(finding["fixedIn"], "3.0.3")
        self.assertEqual(finding["identifiers"], ["CVE-2024-4068"])
        self.assertEqual(finding["message"], "braces: fails to limit the number of characters it can handle")

    def test_takes_the_target_as_the_path_of_a_language_package(self):
        findings = self.findings_of("trivy.json")

        self.assertEqual(findings[0]["path"], "buildnote-app/yarn.lock")
        self.assertIsNone(findings[2]["path"])

    def test_reads_a_trivy_misconfiguration(self):
        misconfiguration = self.findings_of("trivy.json")[3]

        self.assertEqual(misconfiguration["path"], "Dockerfile")
        self.assertEqual(misconfiguration["line"], 1)
        self.assertEqual(misconfiguration["identifiers"], ["AVD-DS-0002"])
        self.assertEqual(
            misconfiguration["message"],
            "Specify at least 1 USER command in Dockerfile with non-root user as argument",
        )
        self.assertIsNone(misconfiguration["package"])

    def test_reads_a_trivy_secret(self):
        secret = self.findings_of("trivy.json")[4]

        self.assertEqual(secret["path"], "deploy/bootstrap.sh")
        self.assertEqual(secret["line"], 14)
        self.assertEqual(secret["message"], "AWS Access Key ID")
        self.assertEqual(secret["identifiers"], [])

    def test_reads_a_trivy_scan_that_found_nothing(self):
        report = json.dumps({"SchemaVersion": 2, "ArtifactName": ".", "Results": None})
        facts = self.collect(self.workspace(**{"trivy.json": report}))

        self.assertEqual(facts["reports"][0]["format"], "trivy")
        self.assertEqual(facts["findings"], [])

    def test_names_the_grype_version_the_descriptor_declares(self):
        report = self.collect(self.workspace(**{"grype.json": GRYPE}))["reports"][0]

        self.assertEqual(report["producer"], {"name": "grype", "version": "0.79.6"})

    def test_reads_every_grype_match(self):
        findings = self.findings_of("grype.json")

        self.assertEqual(
            [(it["id"], it["severity"], it["kind"]) for it in findings],
            [
                ("CVE-2021-44228", "critical", "sca"),
                ("GHSA-4w82-r329-3q67", "medium", "sca"),
                ("CVE-2023-45853", "low", "sca"),
            ],
        )

    def test_reads_the_artifact_a_grype_match_was_found_in(self):
        finding = self.findings_of("grype.json")[0]

        self.assertEqual(finding["package"], {"name": "log4j-core", "version": "2.14.1"})
        self.assertEqual(finding["path"], "/app/lib/log4j-core-2.14.1.jar")
        self.assertEqual(finding["fixedIn"], "2.15.0")
        self.assertIsNone(finding["line"])

    def test_carries_the_related_vulnerabilities_as_identifiers(self):
        findings = self.findings_of("grype.json")

        self.assertEqual(findings[0]["identifiers"], ["CVE-2021-44228", "GHSA-jfh8-c2jp-5v3q"])
        self.assertEqual(findings[1]["identifiers"], ["GHSA-4w82-r329-3q67"])

    def test_reports_no_fix_when_grype_publishes_none(self):
        findings = self.findings_of("grype.json")

        self.assertIsNone(findings[1]["fixedIn"])
        self.assertIsNone(findings[2]["fixedIn"])

    def test_reads_a_grype_scan_that_found_nothing(self):
        report = json.dumps({"matches": [], "descriptor": {"name": "grype", "version": "0.79.6"}})
        facts = self.collect(self.workspace(**{"grype.json": report}))

        self.assertEqual(facts["reports"][0]["format"], "grype")
        self.assertEqual(facts["findings"], [])

    def test_names_osv_scanner_as_the_producer(self):
        report = self.collect(self.workspace(**{"osv.json": fixture("osv.json")}))["reports"][0]

        self.assertEqual(report["producer"], {"name": "osv-scanner", "version": None})

    def test_reads_every_osv_vulnerability_of_every_package(self):
        findings = self.findings_of("osv.json")

        self.assertEqual(
            [(it["id"], it["severity"], it["kind"]) for it in findings],
            [
                ("GHSA-c2qf-rxjj-qqgw", "medium", "sca"),
                ("GHSA-f5x3-32g6-xq36", "high", "sca"),
                ("GHSA-c3h9-896r-86jm", "high", "sca"),
            ],
        )

    def test_takes_the_source_of_an_osv_result_as_the_path(self):
        findings = self.findings_of("osv.json")

        self.assertEqual([it["path"] for it in findings], ["buildnote-app/yarn.lock", "buildnote-app/yarn.lock", "go.mod"])

    def test_reads_the_package_an_osv_vulnerability_affects(self):
        finding = self.findings_of("osv.json")[0]

        self.assertEqual(finding["package"], {"name": "semver", "version": "7.3.7"})
        self.assertEqual(finding["identifiers"], ["GHSA-c2qf-rxjj-qqgw", "CVE-2022-25883"])
        self.assertEqual(finding["fixedIn"], "7.5.2")
        self.assertEqual(finding["message"], "semver vulnerable to Regular Expression Denial of Service")

    def test_scores_an_osv_vulnerability_the_advisory_does_not_grade(self):
        self.assertEqual(self.findings_of("osv.json")[1]["severity"], "high")

    def test_reads_an_osv_scan_that_found_nothing(self):
        facts = self.collect(self.workspace(**{"osv.json": json.dumps({"results": []})}))

        self.assertEqual(facts["reports"][0]["format"], "osv")
        self.assertEqual(facts["findings"], [])

    def test_keeps_every_fingerprint_stable_across_runs(self):
        first = [it["fingerprint"] for it in self.findings_of("trivy.json")]
        second = [it["fingerprint"] for it in self.findings_of("trivy.json")]

        self.assertEqual(first, second)
        self.assertEqual([len(it) for it in first], [16, 16, 16, 16, 16])

    def test_tells_two_findings_of_one_report_apart(self):
        self.assertEqual(len(set(it["fingerprint"] for it in self.findings_of("grype.json"))), 3)

    def test_changes_the_fingerprint_when_the_line_changes(self):
        findings = self.sarif_findings(({"name": "Semgrep"}, [
            result(locations=located(10)),
            result(locations=located(11)),
            result(locations=located(10)),
        ]))

        self.assertNotEqual(findings[0]["fingerprint"], findings[1]["fingerprint"])
        self.assertEqual(findings[0]["fingerprint"], findings[2]["fingerprint"])

    def test_changes_the_fingerprint_when_the_package_version_changes(self):
        report = json.loads(GRYPE)
        report["matches"] = [report["matches"][0], json.loads(json.dumps(report["matches"][0]))]
        report["matches"][1]["artifact"]["version"] = "2.15.0"

        findings = self.findings_of("grype.json", json.dumps(report))

        self.assertNotEqual(findings[0]["fingerprint"], findings[1]["fingerprint"])

    def test_keeps_the_fingerprints_when_the_report_is_reordered(self):
        report = json.loads(GRYPE)
        original = [it["fingerprint"] for it in self.findings_of("grype.json", json.dumps(report))]
        report["matches"].reverse()
        reordered = [it["fingerprint"] for it in self.findings_of("grype.json", json.dumps(report))]

        self.assertEqual(set(original), set(reordered))

    def test_detects_every_report_format_it_reads(self):
        names = ["codeql.sarif", "gitleaks.sarif", "grype.json", "osv.json", "semgrep.sarif", "trivy.json"]

        facts = self.collect(self.workspace(**dict((name, fixture(name)) for name in names)))

        self.assertEqual(
            [(it["path"], it["format"]) for it in facts["reports"]],
            [
                ("codeql.sarif", "sarif"),
                ("gitleaks.sarif", "sarif"),
                ("grype.json", "grype"),
                ("osv.json", "osv"),
                ("semgrep.sarif", "sarif"),
                ("trivy.json", "trivy"),
            ],
        )
        self.assertTrue(all(it["findings"] for it in facts["reports"]))

    def test_detects_a_sarif_report_by_its_runs(self):
        facts = self.collect(self.workspace(**{"report.sarif": json.dumps({"version": "2.1.0", "runs": []})}))

        self.assertEqual(facts["reports"][0]["format"], "sarif")

    def test_gives_every_finding_the_same_shape(self):
        names = ["codeql.sarif", "gitleaks.sarif", "grype.json", "osv.json", "semgrep.sarif", "trivy.json"]

        facts = self.collect(self.workspace(**dict((name, fixture(name)) for name in names)))

        for finding in facts["findings"]:
            self.assertEqual(sorted(finding), FINDING_KEYS)
            self.assertIsInstance(finding["id"], str)
            self.assertIsInstance(finding["message"], str)
            self.assertIsInstance(finding["identifiers"], list)
        self.assertEqual(facts["counts"]["unknown"], 0)
        self.assertEqual(facts["kinds"]["unknown"], 0)

    def test_ignores_a_bill_of_materials_or_an_attestation(self):
        facts = self.collect(self.workspace(**{
            "cyclonedx.sarif": json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}),
            "spdx.sarif": json.dumps({"spdxVersion": "SPDX-2.3", "packages": []}),
            "tag-value.sarif": "SPDXVersion: SPDX-2.3\nPackageName: glibc\n",
            "bom.sarif": '<bom xmlns="http://cyclonedx.org/schema/bom/1.4"><components/></bom>',
            "provenance.sarif": json.dumps({"predicateType": "https://slsa.dev/provenance/v1", "subject": []}),
            "envelope.sarif": json.dumps({"payloadType": "application/vnd.in-toto+json", "payload": "e30="}),
        }))

        self.assertEqual(facts["source"], "none")

    def test_ignores_every_report_it_cannot_read(self):
        facts = self.collect(self.workspace(**dict(("broken-%d.sarif" % number, text) for number, text in enumerate(MALFORMED))))

        self.assertEqual(facts["source"], "none")


if __name__ == "__main__":
    unittest.main()
