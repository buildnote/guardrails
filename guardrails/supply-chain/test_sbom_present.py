#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

BOM = fixture("bom.json")

EMPTY_BOM = """{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}"""


class SbomPresentTest(GuardrailTestCase):
    SCRIPT = "sbom-present.py"
    COLLECT = ["sbom"]

    def test_passes_a_build_that_produced_a_bill_of_materials(self):
        self.assert_passed(self.check(self.workspace(**{"bom.json": BOM})))

    def test_fails_a_build_that_produced_none(self):
        self.assert_violation(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "produced no software bill of materials",
        )

    def test_fails_a_bill_of_materials_that_names_nothing(self):
        self.assert_violation(
            self.check(self.workspace(**{"bom.json": EMPTY_BOM})),
            "names 0 components",
        )

    def test_honours_the_minimum_it_is_given(self):
        self.assert_violation(
            self.check(self.workspace(**{"bom.json": BOM}), minComponents="5"),
            "fewer than the 5 expected",
        )

    def test_skips_a_minimum_that_is_not_a_number(self):
        self.assert_skipped(self.check(self.workspace(**{"bom.json": BOM}), minComponents="lots"), "is not a number")

    def test_says_what_it_looked_for_when_it_fails(self):
        result = self.check(self.workspace(**{"README.md": "widget\n"}))

        self.assertIn("bom.json", result.violations[0]["message"])


if __name__ == "__main__":
    unittest.main()
