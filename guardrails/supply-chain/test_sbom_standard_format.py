#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

CYCLONEDX = '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{"type": "library", "name": "a", "version": "1.0.0"}]}'
NO_VERSION = '{"bomFormat": "CycloneDX", "components": [{"type": "library", "name": "a", "version": "1.0.0"}]}'


class SbomStandardFormatTest(GuardrailTestCase):
    SCRIPT = "sbom-standard-format.py"
    COLLECT = ["sbom"]

    def test_passes_a_cyclonedx_document(self):
        self.assert_passed(self.check(self.workspace(**{"bom.json": CYCLONEDX})))

    def test_fails_a_document_that_declares_no_specification_version(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"bom.json": NO_VERSION})), "declares no specification version"
        )

        self.assertEqual(violation["evidence"], "bom.json")

    def test_takes_no_version_when_it_is_told_to(self):
        directory = self.workspace(**{"bom.json": NO_VERSION})

        self.assert_passed(self.check(directory, requireSpecVersion="false"))

    def test_fails_a_format_it_is_not_configured_to_accept(self):
        directory = self.workspace(**{"bom.json": CYCLONEDX})

        self.assert_violation(self.check(directory, formats="spdx"), "written as cyclonedx rather than as one of spdx")

    def test_skips_a_build_that_produced_none(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "")


if __name__ == "__main__":
    unittest.main()
