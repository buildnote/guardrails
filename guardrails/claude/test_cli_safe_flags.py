#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase


def session(*commands):
    lines = [{"session": {"pid": 42, "startedAt": 1000, "org": "company", "project": "widget",
                          "module": "build", "build": "1_1"}}]
    for index, command in enumerate(commands):
        lines.append({"executed": {"pid": 100 + index, "command": command, "startedAt": 2000 + index}})

    return "".join(json.dumps(line) + "\n" for line in lines)


class CliSafeFlagsTest(GuardrailTestCase):
    SCRIPT = "cli-safe-flags.py"
    COLLECT = ["commands"]

    def check(self, directory, **inputs):
        inputs.setdefault("sessionsDir", "sessions")

        return GuardrailTestCase.check(self, directory, **inputs)

    def monitored(self, *commands):
        return self.workspace(**{"sessions/42.ndjson": session(*commands)})

    def test_passes_an_invocation_that_names_the_tools_it_needs(self):
        directory = self.monitored("claude -p --output-format json --allowedTools Read 'review this diff'")

        self.assert_passed(self.check(directory))

    def test_fails_an_invocation_that_skips_the_approval_step(self):
        directory = self.monitored("claude --dangerously-skip-permissions -p 'deploy to prod'")

        violation = self.assert_violation(self.check(directory), "--dangerously-skip-permissions")

        self.assertEqual(violation["evidence"], "claude --dangerously-skip-permissions -p 'deploy to prod'")

    def test_fails_an_invocation_that_passes_the_flag_with_a_value(self):
        directory = self.monitored("claude --dangerously-skip-permissions=true -p 'go'")

        self.assert_violation(self.check(directory), "--dangerously-skip-permissions")

    def test_reads_claude_wherever_it_was_run_from(self):
        directory = self.monitored("/usr/local/bin/claude --dangerously-skip-permissions -p 'go'")

        self.assert_violation(self.check(directory), "--dangerously-skip-permissions")

    def test_reads_claude_run_through_a_package_runner(self):
        directory = self.monitored("npx claude --dangerously-skip-permissions -p 'go'")

        self.assert_violation(self.check(directory), "--dangerously-skip-permissions")

    def test_takes_the_flags_it_is_given(self):
        directory = self.monitored("claude --yolo -p 'go'")

        self.assert_passed(self.check(directory))
        self.assert_violation(self.check(directory, dangerousFlags="--yolo"), "--yolo")

    def test_reports_a_flag_it_cannot_tell_from_the_prompt_it_was_written_in(self):
        directory = self.monitored("claude -p never use --dangerously-skip-permissions")

        self.assert_violation(self.check(directory), "--dangerously-skip-permissions")

    def test_skips_a_build_that_ran_no_claude(self):
        directory = self.monitored("./gradlew check", "git status")

        self.assert_skipped(self.check(directory), "no Claude CLI invocation was recorded")

    def test_skips_a_build_whose_executions_were_dropped_before_claude_was_seen(self):
        directory = self.monitored("one", "two", "three")

        self.assert_skipped(self.check(directory, maxExecutions=1), "2 executions were left out")

    def test_reports_a_repeated_invocation_once(self):
        directory = self.monitored(
            "claude --dangerously-skip-permissions -p 'go'",
            "claude --dangerously-skip-permissions -p 'go'",
        )

        self.assert_violation(self.check(directory), "--dangerously-skip-permissions")

    def test_skips_a_build_no_monitor_recorded(self):
        self.assert_skipped(self.check(self.workspace()), "no buildnote monitor session was found")


if __name__ == "__main__":
    unittest.main()
