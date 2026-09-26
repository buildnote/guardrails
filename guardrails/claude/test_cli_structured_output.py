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


class CliStructuredOutputTest(GuardrailTestCase):
    SCRIPT = "cli-structured-output.py"
    COLLECT = ["commands"]

    def check(self, directory, **inputs):
        inputs.setdefault("sessionsDir", "sessions")

        return GuardrailTestCase.check(self, directory, **inputs)

    def monitored(self, *commands):
        return self.workspace(**{"sessions/42.ndjson": session(*commands)})

    def test_passes_a_headless_invocation_that_asks_for_json(self):
        self.assert_passed(self.check(self.monitored("claude -p --output-format json 'summarise'")))

    def test_passes_a_headless_invocation_that_asks_for_it_with_an_equals_sign(self):
        self.assert_passed(self.check(self.monitored("claude --print --output-format=stream-json 'summarise'")))

    def test_fails_a_headless_invocation_that_asks_for_nothing(self):
        violation = self.assert_violation(
            self.check(self.monitored("claude -p 'summarise'")), "--output-format json or stream-json"
        )

        self.assertEqual(violation["evidence"], "claude -p 'summarise'")

    def test_fails_a_headless_invocation_that_asks_for_prose(self):
        self.assert_violation(self.check(self.monitored("claude -p --output-format text 'summarise'")), "--output-format")

    def test_fails_a_headless_invocation_whose_format_is_the_last_word(self):
        self.assert_violation(self.check(self.monitored("claude -p 'summarise' --output-format")), "--output-format")

    def test_takes_the_formats_it_is_given(self):
        directory = self.monitored("claude -p --output-format text 'summarise'")

        self.assert_passed(self.check(directory, formats="text"))

    def test_skips_an_invocation_that_is_not_headless(self):
        self.assert_skipped(
            self.check(self.monitored("claude --allowedTools Read")), "no headless Claude CLI invocation"
        )

    def test_skips_a_build_that_ran_no_claude(self):
        self.assert_skipped(self.check(self.monitored("./gradlew check")), "no headless Claude CLI invocation")

    def test_skips_a_build_whose_executions_were_dropped_before_claude_was_seen(self):
        directory = self.monitored("one", "two", "three")

        self.assert_skipped(self.check(directory, maxExecutions=1), "2 executions were left out")

    def test_reports_a_repeated_invocation_once(self):
        directory = self.monitored("claude -p 'summarise'", "claude -p 'summarise'")

        self.assert_violation(self.check(directory), "--output-format")

    def test_skips_a_build_no_monitor_recorded(self):
        self.assert_skipped(self.check(self.workspace()), "no buildnote monitor session was found")


if __name__ == "__main__":
    unittest.main()
