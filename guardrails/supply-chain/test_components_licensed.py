#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def bom(*components):
    return '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [%s]}' % ",".join(components)


def component(name, licence=None):
    licensed = '"licenses": [{"license": {"id": "%s"}}]' % licence if licence else '"licenses": []'

    return '{"type": "library", "name": "%s", "version": "1.0.0", "purl": "pkg:maven/company/%s@1.0.0", %s}' % (
        name, name, licensed
    )


LICENSED = bom(component("log4j-core", "Apache-2.0"), component("kotlin-stdlib", "Apache-2.0"))
HALF = bom(component("log4j-core", "Apache-2.0"), component("mystery"))


class ComponentsLicensedTest(GuardrailTestCase):
    SCRIPT = "components-licensed.py"
    COLLECT = ["sbom"]

    def test_passes_a_bill_of_materials_that_names_every_licence(self):
        self.assert_passed(self.check(self.workspace(**{"bom.json": LICENSED})))

    def test_fails_a_bill_of_materials_that_leaves_licences_out(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"bom.json": HALF})), "names a licence for 50.0% of its components"
        )

        self.assertEqual(violation["evidence"], "1 of 2 components licensed")

    def test_honours_the_share_it_is_given(self):
        directory = self.workspace(**{"bom.json": HALF})

        self.assert_passed(self.check(directory, minPercent=50))
        self.assert_violation(self.check(directory, minPercent=51), "below the 51% expected")

    def test_skips_a_bill_of_materials_that_lists_nothing(self):
        directory = self.workspace(**{"bom.json": '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}'})

        self.assert_skipped(self.check(directory), "lists no components")

    def test_skips_a_build_that_produced_none(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "")

    def test_skips_when_the_share_is_not_a_number(self):
        directory = self.workspace(**{"bom.json": LICENSED})

        self.assert_skipped(self.check(directory, minPercent="most"), "minPercent 'most' is not a number")


if __name__ == "__main__":
    unittest.main()
