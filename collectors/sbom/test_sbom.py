#!/usr/bin/env python3
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

SYFT_TAG_VALUE = fixture("syft-tag-value.spdx")

CYCLONEDX = fixture("cyclonedx-widget.json")

CYCLONEDX_XML = fixture("cyclonedx-widget.xml")

SPDX = fixture("spdx-widget.spdx.json")

SPDX_TAG_VALUE = fixture("spdx-tag-value.spdx")

SARIF = fixture("sarif.json")

CYCLONEDX_FULL = fixture("cyclonedx.json")

CYCLONEDX_XML_FULL = fixture("cyclonedx.xml")

SPDX_FULL = fixture("spdx.spdx.json")


def cyclonedx_with(count):
    components = ",".join(
        """{"type": "library", "name": "widget-%d", "version": "1.0.%d",
            "licenses": [{"license": {"id": "MIT"}}]}""" % (number, number)
        for number in range(count)
    )

    return """{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [%s]}""" % components


class SbomTest(CollectorTestCase):
    COLLECTOR = "sbom"

    def test_reads_a_cyclonedx_bill_of_materials(self):
        facts = self.collect(self.workspace(**{"bom.json": CYCLONEDX}))

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["format"], "cyclonedx")
        self.assertEqual(facts["specVersion"], "1.5")
        self.assertEqual(facts["counts"]["total"], 3)
        self.assertEqual(facts["dropped"], 0)

    def test_names_every_bill_of_materials_it_read(self):
        facts = self.collect(self.workspace(**{"target/bom.json": CYCLONEDX}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "target/bom.json")
        self.assertEqual(report["format"], "cyclonedx")
        self.assertIsNotNone(report["modified"])

    def test_carries_each_component_with_the_licences_it_names(self):
        facts = self.collect(self.workspace(**{"bom.json": CYCLONEDX}))
        component = facts["components"][0]

        self.assertEqual(component["name"], "log4j-core")
        self.assertEqual(component["version"], "2.14.1")
        self.assertEqual(component["purl"], "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1")
        self.assertEqual(component["type"], "library")
        self.assertEqual(component["licenses"], ["Apache-2.0"])
        self.assertIsNone(facts["components"][2]["purl"])

    def test_counts_a_component_under_every_licence_it_names(self):
        facts = self.collect(self.workspace(**{"bom.json": CYCLONEDX}))

        self.assertEqual(facts["counts"]["licensed"], 2)
        self.assertEqual(facts["counts"]["unlicensed"], 1)
        self.assertEqual(facts["licenses"], {"Apache-2.0": 2, "MIT": 1})
        self.assertEqual(sum(facts["licenses"].values()), 3)

    def test_reads_a_cyclonedx_bill_of_materials_written_as_xml(self):
        facts = self.collect(self.workspace(**{"bom.xml": CYCLONEDX_XML}))

        self.assertEqual(facts["format"], "cyclonedx")
        self.assertEqual(facts["specVersion"], "1.4")
        self.assertEqual(facts["counts"]["total"], 1)
        self.assertEqual(facts["components"][0]["name"], "guava")
        self.assertEqual(facts["components"][0]["licenses"], ["Apache-2.0"])

    def test_reads_an_spdx_bill_of_materials(self):
        facts = self.collect(self.workspace(**{"sbom.spdx.json": SPDX}))

        self.assertEqual(facts["format"], "spdx")
        self.assertEqual(facts["specVersion"], "SPDX-2.3")
        self.assertEqual(facts["counts"]["total"], 2)
        self.assertEqual(facts["components"][0]["purl"], "pkg:maven/org.jetbrains.kotlin/kotlin-stdlib@2.1.0")
        self.assertEqual(facts["components"][0]["type"], "library")
        self.assertEqual(facts["licenses"], {"Apache-2.0": 1})

    def test_reads_an_spdx_bill_of_materials_written_as_tag_values(self):
        facts = self.collect(self.workspace(**{"sbom.spdx": SPDX_TAG_VALUE}))

        self.assertEqual(facts["format"], "spdx")
        self.assertEqual(facts["specVersion"], "SPDX-2.2")
        self.assertEqual([it["name"] for it in facts["components"]], ["widget", "slf4j-api"])
        self.assertEqual(facts["components"][0]["licenses"], ["MIT"])
        self.assertEqual(facts["components"][1]["licenses"], [])

    def test_reads_every_bill_of_materials_it_finds(self):
        facts = self.collect(self.workspace(**{"bom.json": CYCLONEDX, "sbom.spdx.json": SPDX}))

        self.assertEqual([report["path"] for report in facts["reports"]], ["bom.json", "sbom.spdx.json"])
        self.assertEqual(facts["counts"]["total"], 5)
        self.assertEqual(facts["format"], "cyclonedx")
        self.assertEqual(facts["specVersion"], "1.5")

    def test_drops_components_over_the_limit_but_keeps_the_counts_whole(self):
        facts = self.collect(self.workspace(**{"bom.json": cyclonedx_with(12)}), maxComponents="5")

        self.assertEqual(facts["counts"]["total"], 12)
        self.assertEqual(facts["licenses"], {"MIT": 12})
        self.assertEqual(len(facts["components"]), 5)
        self.assertEqual(facts["dropped"], 7)

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"bom.json": CYCLONEDX, "sbom.spdx.json": SPDX})

        facts = self.collect(workspace, reports="*.spdx.json")

        self.assertEqual([report["format"] for report in facts["reports"]], ["spdx"])

    def test_ignores_a_bill_of_materials_it_cannot_read(self):
        facts = self.collect(self.workspace(**{"broken.cdx.json": "{ not json", "bom.json": CYCLONEDX}))

        self.assertEqual([report["path"] for report in facts["reports"]], ["bom.json"])

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no bill of materials matched", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_ignores_a_findings_report_that_is_not_a_bill_of_materials(self):
        facts = self.collect(self.workspace(**{"sbom-scan.json": SARIF}))

        self.assertEqual(facts["source"], "none")

    def components_of(self, name, text=None):
        return self.collect(self.workspace(**{name: fixture(name) if text is None else text}))["components"]

    def test_reads_every_component_of_a_json_cyclonedx_bom(self):
        facts = self.collect(self.workspace(**{"cyclonedx.json": CYCLONEDX_FULL}))

        self.assertEqual(facts["format"], "cyclonedx")
        self.assertEqual(facts["specVersion"], "1.5")
        self.assertEqual(
            [(it["name"], it["version"]) for it in facts["components"]],
            [
                ("jackson-databind", "2.15.2"),
                ("lodash", "4.17.21"),
                ("http4k-core", "6.57.2.0"),
                ("kotlin-stdlib", "2.0.20"),
                ("alpine", "3.18.4"),
            ],
        )

    def test_reads_the_purl_type_and_licences_of_a_json_component(self):
        components = self.components_of("cyclonedx.json")

        self.assertEqual(components[0]["purl"], "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.15.2")
        self.assertEqual(components[0]["type"], "library")
        self.assertEqual(components[0]["licenses"], ["Apache-2.0"])
        self.assertEqual(components[1]["licenses"], ["MIT"])
        self.assertEqual(components[2]["licenses"], ["The Apache Software License, Version 2.0"])
        self.assertEqual(components[4]["type"], "operating-system")
        self.assertIsNone(components[4]["purl"])
        self.assertEqual(components[4]["licenses"], [])

    def test_reads_every_component_of_an_xml_cyclonedx_bom(self):
        facts = self.collect(self.workspace(**{"cyclonedx.xml": CYCLONEDX_XML_FULL}))

        self.assertEqual(facts["format"], "cyclonedx")
        self.assertEqual(facts["specVersion"], "1.4")
        self.assertEqual(
            [(it["name"], it["version"], it["type"]) for it in facts["components"]],
            [
                ("commons-lang3", "3.14.0", "library"),
                ("slf4j-api", "2.0.13", "library"),
                ("postgresql", "42.7.3", "library"),
            ],
        )

    def test_reads_the_purl_and_licences_of_an_xml_component(self):
        components = self.components_of("cyclonedx.xml")

        self.assertEqual(components[0]["purl"], "pkg:maven/org.apache.commons/commons-lang3@3.14.0")
        self.assertEqual(components[0]["licenses"], ["Apache-2.0"])
        self.assertEqual(components[1]["licenses"], ["MIT"])
        self.assertEqual(components[2]["licenses"], ["BSD-2-Clause"])

    def test_leaves_the_metadata_component_out(self):
        self.assertNotIn("buildnote-enterprise", [it["name"] for it in self.components_of("cyclonedx.xml")])
        self.assertNotIn("buildnote-cli", [it["name"] for it in self.components_of("cyclonedx.json")])

    def test_reads_every_package_of_a_json_spdx_document(self):
        facts = self.collect(self.workspace(**{"spdx.spdx.json": SPDX_FULL}))

        self.assertEqual(facts["format"], "spdx")
        self.assertEqual(facts["specVersion"], "SPDX-2.3")
        self.assertEqual(
            [(it["name"], it["version"]) for it in facts["components"]],
            [("log4j-core", "2.17.1"), ("zlib", "1.3.1-r0"), ("internal-widget", "")],
        )

    def test_reads_the_purl_type_and_licences_of_a_json_package(self):
        components = self.components_of("spdx.spdx.json")

        self.assertEqual(components[0]["purl"], "pkg:maven/org.apache.logging.log4j/log4j-core@2.17.1")
        self.assertEqual(components[0]["type"], "library")
        self.assertEqual(components[0]["licenses"], ["Apache-2.0"])
        self.assertEqual(components[1]["licenses"], ["Zlib"])
        self.assertIsNone(components[1]["type"])
        self.assertEqual(components[2]["licenses"], [])
        self.assertIsNone(components[2]["purl"])

    def test_reads_every_package_of_a_tag_value_spdx_document(self):
        facts = self.collect(self.workspace(**{"sbom.spdx": SYFT_TAG_VALUE}))

        self.assertEqual(facts["format"], "spdx")
        self.assertEqual(facts["specVersion"], "SPDX-2.3")
        self.assertEqual(
            [(it["name"], it["version"]) for it in facts["components"]],
            [("glibc", "2.36-9+deb12u4"), ("openssl", "3.0.13-1"), ("buildnote-agent", "")],
        )

    def test_reads_the_purl_type_and_licences_of_a_tag_value_package(self):
        components = self.components_of("sbom.spdx", SYFT_TAG_VALUE)

        self.assertEqual(components[0]["purl"], "pkg:deb/debian/glibc@2.36-9+deb12u4?arch=amd64")
        self.assertEqual(components[0]["type"], "library")
        self.assertEqual(components[0]["licenses"], ["LGPL-2.1-only"])
        self.assertEqual(components[1]["licenses"], ["Apache-2.0"])
        self.assertIsNone(components[1]["type"])
        self.assertEqual(components[2]["licenses"], [])
        self.assertIsNone(components[2]["purl"])

    def test_detects_every_bill_of_materials_format_it_reads(self):
        facts = self.collect(self.workspace(**{
            "cyclonedx.json": CYCLONEDX_FULL,
            "cyclonedx.xml": CYCLONEDX_XML_FULL,
            "sbom.spdx": SYFT_TAG_VALUE,
            "spdx.spdx.json": SPDX_FULL,
        }))

        self.assertEqual(
            [(it["path"], it["format"]) for it in facts["reports"]],
            [
                ("cyclonedx.json", "cyclonedx"),
                ("cyclonedx.xml", "cyclonedx"),
                ("sbom.spdx", "spdx"),
                ("spdx.spdx.json", "spdx"),
            ],
        )

    def test_ignores_a_findings_report_or_an_attestation(self):
        facts = self.collect(self.workspace(**{
            "sbom-runs.json": json.dumps({"version": "2.1.0", "runs": []}),
            "sbom-trivy.json": json.dumps({"SchemaVersion": 2, "Results": []}),
            "sbom-grype.json": json.dumps({"matches": []}),
            "sbom-osv.json": json.dumps({"results": []}),
            "sbom-provenance.json": json.dumps({"predicateType": "https://slsa.dev/provenance/v1", "subject": []}),
            "sbom-envelope.json": json.dumps({"payloadType": "application/vnd.in-toto+json", "payload": "e30="}),
        }))

        self.assertEqual(facts["source"], "none")

    def test_ignores_every_bill_of_materials_it_cannot_read(self):
        files = dict(("sbom-%d.json" % number, text) for number, text in enumerate(MALFORMED))
        files.update(dict(("bom-%d.cdx.xml" % number, text) for number, text in enumerate(MALFORMED)))

        facts = self.collect(self.workspace(**files))

        self.assertEqual(facts["source"], "none")


if __name__ == "__main__":
    unittest.main()
