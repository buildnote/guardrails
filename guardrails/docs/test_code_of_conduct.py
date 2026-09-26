#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

ADOPTED = "# Code of Conduct\n\nWe follow the Contributor Covenant 2.1.\n\nReport to conduct@company.com.\n\nThe maintainers enforce it.\n\nAppeals go to the board.\n"


class CodeOfConductTest(GuardrailTestCase):
    SCRIPT = "code-of-conduct.py"
    COLLECT = ["files"]

    def test_passes_a_published_code_of_conduct(self):
        self.assert_passed(self.check(self.workspace(**{"CODE_OF_CONDUCT.md": ADOPTED})))

    def test_fails_a_missing_code_of_conduct(self):
        violation = self.assert_violation(self.check(self.workspace()), "No code of conduct at CODE_OF_CONDUCT.md")

        self.assertEqual(violation["evidence"], "CODE_OF_CONDUCT.md")

    def test_fails_a_stub(self):
        directory = self.workspace(**{"CODE_OF_CONDUCT.md": "# Code of Conduct\n\nBe nice.\n"})

        violation = self.assert_violation(self.check(directory), "has 2 non-blank lines, fewer than the 5 expected")

        self.assertEqual(violation["evidence"], "CODE_OF_CONDUCT.md (2 non-blank lines)")

    def test_honours_the_path_it_is_given(self):
        directory = self.workspace(**{".github/CODE_OF_CONDUCT.md": ADOPTED})

        self.assert_passed(self.check(directory, path=".github/CODE_OF_CONDUCT.md"))

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{"CODE_OF_CONDUCT.md": ADOPTED})

        self.assert_skipped(self.check(directory, minLines="five"), "minLines 'five' is not a number")


if __name__ == "__main__":
    unittest.main()
