#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def bom(*components):
    return '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [%s]}' % ",".join(components)


def component(name, licence):
    return (
        '{"type": "library", "name": "%s", "version": "1.0.0", "purl": "pkg:maven/company/%s@1.0.0", '
        '"licenses": [{"license": {"id": "%s"}}]}' % (name, name, licence)
    )


PERMISSIVE = bom(component("log4j-core", "Apache-2.0"), component("kotlin-stdlib", "MIT"))
COPYLEFT = bom(component("log4j-core", "Apache-2.0"), component("ghostscript", "AGPL-3.0-or-later"))


class DisallowedLicensesTest(GuardrailTestCase):
    SCRIPT = "disallowed-licenses.py"
    COLLECT = ["sbom"]

    def test_passes_permissively_licensed_components(self):
        self.assert_passed(self.check(self.workspace(**{"bom.json": PERMISSIVE})))

    def test_fails_a_refused_licence(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"bom.json": COPYLEFT})), "licensed under AGPL-3.0-or-later"
        )

        self.assertEqual(violation["evidence"], "ghostscript 1.0.0 (AGPL-3.0-or-later)")

    def test_honours_the_licences_it_is_given(self):
        directory = self.workspace(**{"bom.json": COPYLEFT})

        self.assert_passed(self.check(directory, licenses="SSPL-1.0"))
        self.assert_violation(self.check(directory, licenses="MIT,AGPL-3.0"), "ghostscript")

    def test_skips_when_the_team_refuses_none(self):
        self.assert_skipped(self.check(self.workspace(**{"bom.json": COPYLEFT}), licenses=" "), "refuses")

    def test_skips_a_build_that_produced_none(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"})), "")


if __name__ == "__main__":
    unittest.main()
