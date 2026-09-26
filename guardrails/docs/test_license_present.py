#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

LICENCE = "Copyright (c) 2026 Company Ltd. All rights reserved.\n"


class LicensePresentTest(GuardrailTestCase):
    SCRIPT = "license-present.py"
    COLLECT = ["files"]

    def test_passes_a_repository_with_a_licence(self):
        self.assert_passed(self.check(self.workspace(**{"LICENSE": LICENCE})))

    def test_passes_a_licence_under_another_accepted_name(self):
        self.assert_passed(self.check(self.workspace(**{"LICENSE.md": LICENCE})))

    def test_fails_a_repository_with_none(self):
        self.assert_violation(self.check(self.workspace(**{"README.md": "widget\n"})), "states no licence")

    def test_names_every_path_it_looked_for(self):
        result = self.check(self.workspace(**{"README.md": "widget\n"}))

        self.assertIn("COPYING", result.violations[0]["message"])

    def test_honours_the_paths_it_is_given(self):
        self.assert_passed(self.check(self.workspace(**{"COPYING": LICENCE}), paths="COPYING"))
        self.assert_violation(self.check(self.workspace(**{"COPYING": LICENCE}), paths="LICENSE"), "states no licence")


if __name__ == "__main__":
    unittest.main()
