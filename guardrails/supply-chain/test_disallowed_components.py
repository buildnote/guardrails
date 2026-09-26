#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

BOM = (
    '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": ['
    '{"type": "library", "name": "log4j-core", "version": "2.14.1", '
    '"purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1", "licenses": []},'
    '{"type": "library", "name": "event-stream", "version": "3.3.6", '
    '"purl": "pkg:npm/event-stream@3.3.6", "licenses": []}]}'
)


class DisallowedComponentsTest(GuardrailTestCase):
    SCRIPT = "disallowed-components.py"
    COLLECT = ["sbom"]

    def test_skips_when_the_team_refuses_none(self):
        self.assert_skipped(self.check(self.workspace(**{"bom.json": BOM})), "no component was named")

    def test_fails_a_refused_component_by_name(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"bom.json": BOM}), components="event-stream"), "decided against"
        )

        self.assertEqual(violation["evidence"], "event-stream 3.3.6")

    def test_fails_a_refused_component_by_package_url(self):
        self.assert_violation(
            self.check(self.workspace(**{"bom.json": BOM}), components="pkg:npm/event-stream"), "event-stream 3.3.6"
        )

    def test_passes_a_bill_of_materials_naming_none_of_them(self):
        self.assert_passed(self.check(self.workspace(**{"bom.json": BOM}), components="left-pad"))

    def test_skips_a_build_that_produced_none(self):
        self.assert_skipped(self.check(self.workspace(**{"README.md": "widget\n"}), components="left-pad"), "")


if __name__ == "__main__":
    unittest.main()
