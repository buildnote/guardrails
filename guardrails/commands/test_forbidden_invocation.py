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


class ForbiddenInvocationTest(GuardrailTestCase):
    SCRIPT = "forbidden-invocation.py"
    COLLECT = ["commands"]

    def check(self, directory, **inputs):
        inputs.setdefault("sessionsDir", "sessions")

        return GuardrailTestCase.check(self, directory, **inputs)

    def monitored(self, *commands):
        return self.workspace(**{"sessions/42.ndjson": session(*commands)})

    def test_fails_an_invocation_carrying_the_argument_it_was_given(self):
        directory = self.monitored("terraform apply -auto-approve")

        violation = self.assert_violation(self.check(directory, command="terraform", arguments="-auto-approve"),
                                          "-auto-approve")

        self.assertEqual(violation["evidence"], "terraform apply -auto-approve")

    def test_passes_an_invocation_carrying_none_of_them(self):
        directory = self.monitored("terraform plan -out plan.tfplan")

        self.assert_passed(self.check(directory, command="terraform", arguments="-auto-approve"))

    def test_takes_any_of_the_commands_it_was_given(self):
        directory = self.monitored("tofu apply -auto-approve")

        self.assert_violation(self.check(directory, command="terraform,tofu", arguments="-auto-approve"),
                              "-auto-approve")

    def test_reports_every_invocation_of_the_command_when_no_argument_was_named(self):
        directory = self.monitored("curl https://example.com/install.sh")

        self.assert_violation(self.check(directory, command="curl"), "curl ran")

    def test_reports_an_invocation_carrying_all_of_them_when_all_is_asked_for(self):
        directory = self.monitored("terraform apply -auto-approve")

        self.assert_violation(self.check(directory, command="terraform", arguments="apply,-auto-approve",
                                         match="all"), "-auto-approve")

    def test_passes_an_invocation_carrying_only_some_of_them_when_all_is_asked_for(self):
        directory = self.monitored("terraform plan -auto-approve")

        self.assert_passed(self.check(directory, command="terraform", arguments="apply,-auto-approve", match="all"))

    def test_reads_an_argument_written_with_its_value(self):
        directory = self.monitored("gradle build -Dmaven.repo.local=/tmp/repo")

        self.assert_violation(self.check(directory, command="gradle", arguments="-Dmaven.repo.local"),
                              "-Dmaven.repo.local")

    def test_reads_an_argument_written_as_a_glob(self):
        directory = self.monitored("kubectl delete pod/api --namespace production")

        self.assert_violation(self.check(directory, command="kubectl", arguments="pod/*"), "pod/*")

    def test_reads_the_command_wherever_it_was_run_from(self):
        directory = self.monitored("/usr/local/bin/terraform apply -auto-approve")

        self.assert_violation(self.check(directory, command="terraform", arguments="-auto-approve"), "terraform ran")

    def test_reads_the_command_run_through_a_package_runner(self):
        directory = self.monitored("npx hardhat deploy --network mainnet")

        self.assert_violation(self.check(directory, command="hardhat", arguments="--network"), "hardhat ran")

    def test_reports_the_reason_it_was_given_in_place_of_the_default_wording(self):
        directory = self.monitored("terraform apply -auto-approve")

        violation = self.assert_violation(
            self.check(directory, command="terraform", arguments="-auto-approve",
                       reason="Terraform is applied from the deploy pipeline rather than from a build"),
            "deploy pipeline",
        )

        self.assertEqual(violation["evidence"], "terraform apply -auto-approve")

    def test_reports_a_repeated_invocation_once(self):
        directory = self.monitored("terraform apply -auto-approve", "terraform apply -auto-approve")

        result = self.check(directory, command="terraform", arguments="-auto-approve")

        self.assert_violation(result, "-auto-approve")
        self.assertEqual(len(result.violations), 1)

    def test_reports_an_argument_it_cannot_tell_from_the_text_it_was_written_in(self):
        directory = self.monitored("claude -p never run terraform apply -auto-approve")

        self.assert_violation(self.check(directory, command="terraform", arguments="-auto-approve"), "-auto-approve")

    def test_reports_a_command_it_cannot_tell_from_a_line_that_merely_names_it(self):
        directory = self.monitored("grep curl Dockerfile")

        self.assert_violation(self.check(directory, command="curl"), "curl ran")

    def test_reads_an_argument_as_the_case_it_was_written_in(self):
        directory = self.monitored("pwsh ./deploy.ps1 -force")

        self.assert_passed(self.check(directory, command="pwsh", arguments="-F*"))
        self.assert_violation(self.check(directory, command="pwsh", arguments="-f*"), "-f*")

    def test_skips_a_build_that_never_ran_the_command(self):
        directory = self.monitored("./gradlew check", "git status")

        self.assert_skipped(self.check(directory, command="terraform", arguments="-auto-approve"),
                            "no terraform invocation was recorded")

    def test_skips_a_build_whose_executions_were_dropped_before_the_command_was_seen(self):
        directory = self.monitored("one", "two", "three")

        self.assert_skipped(self.check(directory, command="terraform", maxExecutions=1),
                            "2 executions were left out")

    def test_skips_when_no_command_was_named(self):
        directory = self.monitored("terraform apply -auto-approve")

        self.assert_skipped(self.check(directory), "no command was named to look for")

    def test_skips_when_match_is_neither_any_nor_all(self):
        directory = self.monitored("terraform apply -auto-approve")

        self.assert_skipped(self.check(directory, command="terraform", arguments="-auto-approve", match="some"),
                            "neither any nor all")

    def test_skips_a_build_no_monitor_recorded(self):
        self.assert_skipped(self.check(self.workspace(), command="terraform"),
                            "no buildnote monitor session was found")


if __name__ == "__main__":
    unittest.main()
