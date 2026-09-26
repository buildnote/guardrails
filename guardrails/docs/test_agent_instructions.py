#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

INSTRUCTIONS = "\n".join("Line %d of instructions that say something." % line for line in range(1, 13))
PATHS = "AGENTS.md,CLAUDE.md,.github/copilot-instructions.md"


class AgentInstructionsTest(GuardrailTestCase):
    SCRIPT = "agent-instructions.py"
    COLLECT = ["files"]

    def check(self, directory, **inputs):
        inputs.setdefault("paths", PATHS)

        return GuardrailTestCase.check(self, directory, **inputs)

    def test_passes_an_instruction_file_that_says_something(self):
        self.assert_passed(self.check(self.workspace(**{"AGENTS.md": INSTRUCTIONS})))

    def test_fails_a_repository_that_instructs_nobody(self):
        violation = self.assert_violation(self.check(self.workspace()), "The repository instructs no coding agent")

        self.assertEqual(violation["evidence"], "AGENTS.md")

    def test_accepts_any_of_the_paths_it_is_given(self):
        self.assert_passed(self.check(self.workspace(**{"CLAUDE.md": INSTRUCTIONS})))
        self.assert_passed(
            self.check(self.workspace(**{".github/copilot-instructions.md": INSTRUCTIONS}))
        )

    def test_fails_instructions_shorter_than_the_floor(self):
        directory = self.workspace(**{"AGENTS.md": "# AGENTS.md\n\nBe careful.\n"})

        violation = self.assert_violation(self.check(directory), "have 2 non-blank lines, fewer than the 10 expected")

        self.assertEqual(violation["evidence"], "AGENTS.md (2 non-blank lines)")

    def test_fails_instructions_past_the_ceiling(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})

        self.assert_violation(
            self.check(directory, maxLines=5), "have 12 non-blank lines, more than the 5 that will be attended to"
        )

    def test_takes_no_ceiling_at_all(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})

        self.assert_passed(self.check(directory, maxLines=0))

    def test_skips_when_the_floor_is_not_a_number(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})

        self.assert_skipped(self.check(directory, minLines="ten"), "minLines 'ten' is not a number")


if __name__ == "__main__":
    unittest.main()
