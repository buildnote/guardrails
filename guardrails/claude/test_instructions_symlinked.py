#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

INSTRUCTIONS = "# AGENTS.md\n\nRun `./gradlew check`.\n"


class InstructionsSymlinkedTest(GuardrailTestCase):
    SCRIPT = "instructions-symlinked.py"
    COLLECT = ["files"]

    def check(self, directory, **inputs):
        inputs.setdefault("paths", "CLAUDE.md,AGENTS.md")

        return GuardrailTestCase.check(self, directory, **inputs)

    def link(self, directory, name, target):
        try:
            os.symlink(target.replace("/", os.sep), os.path.join(directory, name))
        except OSError as error:
            self.skip("this runner cannot create a symbolic link: %s" % error)

        return directory

    def test_passes_an_alias_pointing_at_the_instructions(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})
        self.link(directory, "CLAUDE.md", "AGENTS.md")

        self.assert_passed(self.check(directory))

    def test_fails_a_second_copy_of_the_instructions(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS, "CLAUDE.md": INSTRUCTIONS})

        violation = self.assert_violation(self.check(directory), "is a file of its own rather than a symbolic link")

        self.assertEqual(violation["evidence"], "CLAUDE.md")

    def test_fails_instructions_claude_never_reads(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})

        self.assert_violation(self.check(directory), "Claude Code reads no instructions here")

    def test_fails_an_alias_pointing_at_nothing(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})
        self.link(directory, "CLAUDE.md", "INSTRUCTIONS.md")

        self.assert_violation(self.check(directory), "symbolic link to INSTRUCTIONS.md, which is not there")

    def test_fails_an_alias_pointing_somewhere_else(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS, "docs/agents.md": INSTRUCTIONS})
        self.link(directory, "CLAUDE.md", "docs/agents.md")

        self.assert_violation(self.check(directory), "symbolic link to docs/agents.md rather than to AGENTS.md")

    def test_reads_an_alias_that_reaches_the_instructions_from_another_directory(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS, "docs/index.md": "# Docs\n"})
        self.link(directory, "docs/CLAUDE.md", "../AGENTS.md")

        self.assert_passed(self.check(directory, paths="docs/CLAUDE.md,AGENTS.md"))

    def test_skips_a_repository_that_keeps_no_instructions(self):
        self.assert_skipped(self.check(self.workspace()), "AGENTS.md is not there")

    def test_skips_a_paths_naming_only_an_alias(self):
        directory = self.workspace(**{"AGENTS.md": INSTRUCTIONS})

        self.assert_skipped(self.check(directory, paths="CLAUDE.md"), "rather than an alias and the file")


if __name__ == "__main__":
    unittest.main()
