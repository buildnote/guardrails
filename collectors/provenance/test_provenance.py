#!/usr/bin/env python3
import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

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

SLSA_V1 = fixture("slsa-v1.json")

SLSA_V02 = fixture("slsa-v02.json")

BARE = fixture("bare.json")

URL_SAFE_STATEMENT = fixture("url-safe-statement.json")

INTOTO = fixture("intoto.json")


def envelope(statement):
    return json.dumps({
        "payloadType": "application/vnd.in-toto+json",
        "payload": base64.b64encode(statement.encode("utf-8")).decode("ascii"),
        "signatures": [{"keyid": "company-release", "sig": "MEUCIQDwidgetSignatureBytes=="}],
    })


class ProvenanceTest(CollectorTestCase):
    COLLECTOR = "provenance"

    def test_reads_a_bare_in_toto_statement(self):
        facts = self.collect(self.workspace(**{"attestation.json": BARE}))
        attestation = facts["attestations"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["counts"]["total"], 1)
        self.assertEqual(facts["counts"]["signed"], 0)
        self.assertEqual(attestation["predicateType"], "https://spdx.dev/Document")
        self.assertEqual(attestation["envelope"], False)
        self.assertIsNone(attestation["builder"])
        self.assertIsNone(attestation["sourceUri"])
        self.assertIsNone(attestation["sourceDigest"])

    def test_names_every_file_it_read(self):
        facts = self.collect(self.workspace(**{"build/provenance.json": SLSA_V1}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "build/provenance.json")
        self.assertEqual(report["format"], "intoto")
        self.assertIsNotNone(report["modified"])

    def test_reads_slsa_provenance_v1(self):
        facts = self.collect(self.workspace(**{"provenance.json": SLSA_V1}))
        attestation = facts["attestations"][0]

        self.assertEqual(attestation["predicateType"], "https://slsa.dev/provenance/v1")
        self.assertEqual(attestation["builder"], "https://github.com/actions/runner/github-hosted")
        self.assertEqual(attestation["sourceUri"], "git+https://github.com/company/widget@refs/tags/v1.4.0")
        self.assertEqual(attestation["sourceDigest"], "9b2c1d4e6f8a0b3c5d7e9f1a2b4c6d8e0f1a2b3c")

    def test_reads_slsa_provenance_v0_2(self):
        facts = self.collect(self.workspace(**{"attestation-v02.json": SLSA_V02}))
        attestation = facts["attestations"][0]

        self.assertEqual(attestation["predicateType"], "https://slsa.dev/provenance/v0.2")
        self.assertEqual(attestation["builder"], "https://buildkite.com/company/widget")
        self.assertEqual(attestation["sourceUri"], "git+https://github.com/company/widget@refs/heads/main")
        self.assertEqual(attestation["sourceDigest"], "1122334455667788990011223344556677889900")

    def test_carries_every_subject_with_its_digest(self):
        facts = self.collect(self.workspace(**{"attestation-v02.json": SLSA_V02}))
        subjects = facts["attestations"][0]["subjects"]

        self.assertEqual([subject["name"] for subject in subjects], ["widget-image", "widget-1.4.0.jar"])
        self.assertEqual(
            subjects[0]["digest"],
            {"sha256": "5c8f2b1d3e4a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e"},
        )
        self.assertEqual(subjects[1]["digest"], {"sha512": "0a1b2c3d"})

    def test_reads_a_statement_inside_a_dsse_envelope(self):
        facts = self.collect(self.workspace(**{"widget.att.json": envelope(SLSA_V1)}))
        attestation = facts["attestations"][0]

        self.assertEqual(facts["counts"]["total"], 1)
        self.assertEqual(facts["counts"]["signed"], 1)
        self.assertEqual(attestation["envelope"], True)
        self.assertEqual(attestation["predicateType"], "https://slsa.dev/provenance/v1")
        self.assertEqual(attestation["subjects"][0]["name"], "widget-1.4.0.jar")

    def test_reads_every_attestation_a_jsonl_file_carries(self):
        lines = "\n".join([envelope(SLSA_V1), envelope(SLSA_V02)]) + "\n"

        facts = self.collect(self.workspace(**{"widget.intoto.jsonl": lines}))

        self.assertEqual(len(facts["reports"]), 1)
        self.assertEqual(facts["counts"]["total"], 2)
        self.assertEqual(facts["counts"]["signed"], 2)
        self.assertEqual(
            [it["predicateType"] for it in facts["attestations"]],
            ["https://slsa.dev/provenance/v1", "https://slsa.dev/provenance/v0.2"],
        )

    def test_reads_every_file_it_finds(self):
        workspace = self.workspace(**{"provenance.json": SLSA_V1, "widget.att.json": envelope(SLSA_V02)})

        facts = self.collect(workspace)

        self.assertEqual([report["path"] for report in facts["reports"]], ["provenance.json", "widget.att.json"])
        self.assertEqual(facts["counts"]["total"], 2)
        self.assertEqual(facts["counts"]["signed"], 1)

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"provenance.json": SLSA_V1, "widget.att.json": envelope(SLSA_V02)})

        facts = self.collect(workspace, reports="*.att.json")

        self.assertEqual([report["path"] for report in facts["reports"]], ["widget.att.json"])

    def test_ignores_an_attestation_it_cannot_read(self):
        workspace = self.workspace(**{
            "broken.dsse.json": """{"payloadType": "application/vnd.in-toto+json", "payload": "@@@"}""",
            "torn.att.json": "{ not json",
            "provenance.json": SLSA_V1,
        })

        facts = self.collect(workspace)

        self.assertEqual([report["path"] for report in facts["reports"]], ["provenance.json"])
        self.assertEqual(facts["counts"]["total"], 1)

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no attestation matched", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_ignores_a_document_that_is_not_an_attestation(self):
        report = """{"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0", "runs": []}"""

        facts = self.collect(self.workspace(**{"attestation-scan.json": report}))

        self.assertEqual(facts["source"], "none")

    def attestation_of(self, text, name="provenance.json"):
        return self.collect(self.workspace(**{name: text}))["attestations"][0]

    def without_envelope(self, attestation):
        return dict((key, value) for key, value in attestation.items() if key != "envelope")

    def test_reads_a_bare_slsa_v1_statement(self):
        attestation = self.attestation_of(INTOTO)

        self.assertEqual(attestation["predicateType"], "https://slsa.dev/provenance/v1")
        self.assertEqual(
            attestation["builder"],
            "https://github.com/slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@refs/tags/v2.0.0",
        )
        self.assertEqual(attestation["sourceUri"], "git+https://github.com/buildnote/buildnote@refs/heads/main")
        self.assertEqual(attestation["sourceDigest"], "c1124e7a5b0f7d2a4e6c9018d3fe4471a2b5c6d7")

    def test_reads_every_subject_of_a_statement(self):
        subjects = self.attestation_of(INTOTO)["subjects"]

        self.assertEqual([it["name"] for it in subjects], ["buildnote-cli-1.42.0.jar", "buildnote-cli-1.42.0.jar.asc"])
        self.assertEqual(
            subjects[0]["digest"],
            {"sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"},
        )

    def test_reads_a_slsa_v0_2_statement(self):
        attestation = self.attestation_of(fixture("intoto_slsa02.json"))

        self.assertEqual(attestation["predicateType"], "https://slsa.dev/provenance/v0.2")
        self.assertEqual(attestation["builder"], "https://github.com/Attestations/GitHubHostedActions@v1")
        self.assertEqual(attestation["sourceUri"], "git+https://github.com/buildnote/buildnote@refs/heads/main")
        self.assertEqual(attestation["sourceDigest"], "8c90e284f2b1a70dfd51c3b6a9e4f0dd12ab34cd")
        self.assertEqual([it["name"] for it in attestation["subjects"]], ["buildnote-collector.zip"])

    def test_reads_the_same_statement_out_of_a_dsse_envelope(self):
        for name in ["intoto.json", "intoto_slsa02.json"]:
            bare = self.attestation_of(fixture(name))
            wrapped = self.attestation_of(envelope(fixture(name)), "widget.att.json")

            self.assertEqual(self.without_envelope(wrapped), self.without_envelope(bare), name)
            self.assertEqual(wrapped["envelope"], True, name)

    def test_reads_an_envelope_whose_payload_is_url_safe_and_unpadded(self):
        payload = base64.urlsafe_b64encode(URL_SAFE_STATEMENT.encode("utf-8")).decode("ascii").rstrip("=")
        wrapped = json.dumps({"payloadType": "application/vnd.in-toto+json", "payload": payload})

        self.assertTrue(set("-_") & set(payload), payload)
        self.assertEqual(
            self.without_envelope(self.attestation_of(wrapped, "widget.dsse.json")),
            self.without_envelope(self.attestation_of(URL_SAFE_STATEMENT)),
        )
        self.assertEqual(self.attestation_of(wrapped, "widget.dsse.json")["predicateType"], "https://spdx.dev/Document")

    def test_reads_a_subject_that_carries_no_digest(self):
        attestation = self.attestation_of(json.dumps({
            "_type": "https://in-toto.io/Statement/v1",
            "predicateType": "https://spdx.dev/Document",
            "subject": [{"name": "sbom.spdx.json", "digest": {}}],
            "predicate": {},
        }))

        self.assertIsNone(attestation["builder"])
        self.assertIsNone(attestation["sourceUri"])
        self.assertIsNone(attestation["sourceDigest"])
        self.assertEqual(attestation["subjects"], [{"name": "sbom.spdx.json", "digest": {}}])

    def test_detects_a_bare_statement_and_a_dsse_envelope(self):
        workspace = self.workspace(**{
            "provenance.json": INTOTO,
            "widget.att.json": envelope(INTOTO),
        })

        facts = self.collect(workspace)

        self.assertEqual([(it["path"], it["format"]) for it in facts["reports"]], [
            ("provenance.json", "intoto"),
            ("widget.att.json", "intoto"),
        ])

    def test_ignores_a_findings_report_or_a_bill_of_materials(self):
        facts = self.collect(self.workspace(**{
            "provenance-runs.json": json.dumps({"version": "2.1.0", "runs": [], "predicateType": "p"}),
            "provenance-cyclonedx.json": json.dumps({"bomFormat": "CycloneDX", "predicateType": "p", "subject": []}),
            "provenance-spdx.json": json.dumps({"spdxVersion": "SPDX-2.3", "predicateType": "p", "subject": []}),
            "provenance-trivy.json": json.dumps({"SchemaVersion": 2, "Results": []}),
            "provenance-grype.json": json.dumps({"matches": []}),
            "provenance-osv.json": json.dumps({"results": []}),
            "provenance-subject.json": json.dumps({"subject": []}),
        }))

        self.assertEqual(facts["source"], "none")

    def test_ignores_every_attestation_it_cannot_read(self):
        broken = MALFORMED + [
            json.dumps({"payloadType": "application/vnd.in-toto+json", "payload": "!!! not base64 !!!"}),
            json.dumps({"payloadType": "application/vnd.in-toto+json", "payload": base64.b64encode(b"nope").decode()}),
        ]

        facts = self.collect(self.workspace(**dict(("attestation-%d.json" % number, text) for number, text in enumerate(broken))))

        self.assertEqual(facts["source"], "none")


if __name__ == "__main__":
    unittest.main()
