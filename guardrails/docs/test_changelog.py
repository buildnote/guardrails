#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

KEPT = "# Changelog\n\n## 1.4.0\n\n### Added\n- Token rotation on the public API.\n\n### Fixed\n- Expired sessions were accepted once more.\n"


class ChangelogTest(GuardrailTestCase):
    SCRIPT = "changelog.py"
    COLLECT = ["files"]

    def check(self, directory, **inputs):
        inputs.setdefault("path", "CHANGELOG.md")

        return GuardrailTestCase.check(self, directory, **inputs)

    def test_passes_a_changelog_that_says_something(self):
        self.assert_passed(self.check(self.workspace(**{"CHANGELOG.md": KEPT})))

    def test_fails_a_missing_changelog(self):
        violation = self.assert_violation(self.check(self.workspace()), "No changelog at CHANGELOG.md")

        self.assertEqual(violation["evidence"], "CHANGELOG.md")

    def test_fails_a_changelog_shorter_than_the_floor(self):
        directory = self.workspace(**{"CHANGELOG.md": "# Changelog\n\nNothing yet.\n"})

        violation = self.assert_violation(self.check(directory), "has 2 non-blank lines, fewer than the 5 expected")

        self.assertEqual(violation["evidence"], "CHANGELOG.md (2 non-blank lines)")

    def test_honours_the_path_it_is_given(self):
        directory = self.workspace(**{"docs/releases.md": KEPT})

        self.assert_passed(self.check(directory, path="docs/releases.md"))
        self.assert_violation(self.check(directory), "No changelog at CHANGELOG.md")

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{"CHANGELOG.md": KEPT})

        self.assert_skipped(self.check(directory, minLines="five"), "minLines 'five' is not a number")


if __name__ == "__main__":
    unittest.main()
