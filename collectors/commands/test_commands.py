#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase

BUILD = "18342119027_1"


def line(record):
    return json.dumps(record) + "\n"


def session(pid=4242, build=BUILD, started=1000, command=None, executed=(), closed=None, module="build"):
    header = {
        "pid": pid,
        "startedAt": started,
        "org": "company",
        "project": "widget",
        "module": module,
        "build": build,
    }
    if command is not None:
        header["command"] = command

    text = line({"session": header})
    for record in executed:
        text += line(record)
    if closed is not None:
        text += line({"closedAt": closed})

    return text


def executed(pid, command, started):
    return {"executed": {"pid": pid, "command": command, "startedAt": started}}


def exited(pid, exit_code, completed):
    return {"exited": {"pid": pid, "completedAt": completed, "exitCode": exit_code}}


class CommandsCollectorTest(CollectorTestCase):
    COLLECTOR = "commands"

    def collect(self, directory, **inputs):
        inputs.setdefault("sessionsDir", "sessions")
        os.environ["BUILDNOTE_BUILD"] = inputs.pop("build", BUILD)

        return CollectorTestCase.collect(self, directory, **inputs)

    def workspace_with(self, **sessions):
        return self.workspace(**{"sessions/%s" % name: text for name, text in sessions.items()})

    def test_collects_the_commands_a_running_monitor_has_recorded(self):
        directory = self.workspace_with(**{"4242.ndjson": session(
            command="./gradlew check",
            executed=[
                executed(11, "git rev-parse HEAD", 2000),
                exited(11, 0, 2100),
                executed(12, "claude -p 'review'", 3000),
            ],
        )})

        facts = self.collect(directory)

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["monitor"]["running"], True)
        self.assertEqual(facts["monitor"]["matched"], "build")
        self.assertEqual(facts["monitor"]["sessions"], 1)
        self.assertEqual(facts["monitor"]["pid"], 4242)
        self.assertEqual(facts["monitor"]["startedAt"], 1000)
        self.assertEqual(facts["monitor"]["closedAt"], None)
        self.assertEqual(facts["monitor"]["build"], BUILD)
        self.assertEqual(facts["monitor"]["module"], "build")
        self.assertEqual(facts["monitor"]["command"], "./gradlew check")
        self.assertEqual(facts["commands"], [
            {"command": "git rev-parse HEAD", "pid": 11, "startedAt": 2000, "durationMs": 100, "exitCode": 0},
            {"command": "claude -p 'review'", "pid": 12, "startedAt": 3000, "durationMs": None, "exitCode": None},
        ])
        self.assertEqual(facts["counts"], {"executions": 2, "commands": 2})
        self.assertEqual(facts["dropped"], 0)

    def test_names_the_session_it_read(self):
        directory = self.workspace_with(**{"4242.ndjson": session()})

        report = self.collect(directory)["reports"][0]

        self.assertTrue(report["path"].endswith("sessions/4242.ndjson"))
        self.assertTrue(report["modified"])
        self.assertEqual(report["format"], "monitor-session")

    def test_collects_a_repeated_command_once_per_execution(self):
        directory = self.workspace_with(**{"4242.ndjson": session(executed=[
            executed(11, "git status", 2000),
            exited(11, 0, 2100),
            executed(12, "git status", 4000),
            exited(12, 1, 4100),
        ])})

        facts = self.collect(directory)

        self.assertEqual([(it["pid"], it["exitCode"]) for it in facts["commands"]], [(11, 0), (12, 1)])
        self.assertEqual(facts["counts"], {"executions": 2, "commands": 1})

    def test_collects_no_exit_code_for_a_command_still_running(self):
        directory = self.workspace_with(**{"4242.ndjson": session(executed=[
            executed(11, "./gradlew check", 2000),
        ])})

        reported = self.collect(directory)["commands"][0]

        self.assertEqual(reported["exitCode"], None)
        self.assertEqual(reported["durationMs"], None)

    def test_collects_the_second_execution_of_a_reused_process(self):
        directory = self.workspace_with(**{"4242.ndjson": session(executed=[
            executed(11, "/bin/sh -c ./build", 2000),
            exited(11, None, 2100),
            executed(11, "./build", 2100),
            exited(11, 0, 2500),
        ])})

        commands = self.collect(directory)["commands"]

        self.assertEqual([it["command"] for it in commands], ["/bin/sh -c ./build", "./build"])
        self.assertEqual([it["exitCode"] for it in commands], [None, 0])
        self.assertEqual([it["durationMs"] for it in commands], [100, 400])

    def test_collects_a_monitor_that_has_finished(self):
        directory = self.workspace_with(**{"4242.ndjson": session(
            executed=[executed(11, "git status", 2000)],
            closed=9000,
        )})

        monitor = self.collect(directory)["monitor"]

        self.assertEqual(monitor["running"], False)
        self.assertEqual(monitor["closedAt"], 9000)

    def test_collects_no_command_for_a_monitor_that_attached_to_a_process(self):
        directory = self.workspace_with(**{"4242.ndjson": session()})

        self.assertEqual(self.collect(directory)["monitor"]["command"], None)

    def test_reads_the_session_recording_this_build(self):
        directory = self.workspace_with(**{
            "1.ndjson": session(pid=1, build="another_build", started=8000,
                                executed=[executed(11, "somebody else", 8100)]),
            "2.ndjson": session(pid=2, started=1000, executed=[executed(12, "git status", 1100)]),
        })

        facts = self.collect(directory)

        self.assertEqual(facts["monitor"]["pid"], 2)
        self.assertEqual(facts["monitor"]["matched"], "build")
        self.assertEqual(facts["monitor"]["sessions"], 2)

    def test_reads_the_running_session_when_none_records_this_build(self):
        directory = self.workspace_with(**{
            "1.ndjson": session(pid=1, build="one", started=8000, closed=8500),
            "2.ndjson": session(pid=2, build="two", started=1000),
        })

        facts = self.collect(directory, build="neither")

        self.assertEqual(facts["monitor"]["pid"], 2)
        self.assertEqual(facts["monitor"]["matched"], "recent")

    def test_keeps_the_earliest_executions_and_counts_the_rest_as_dropped(self):
        directory = self.workspace_with(**{"4242.ndjson": session(executed=[
            executed(11, "one", 2000),
            executed(12, "two", 3000),
            executed(13, "three", 4000),
            executed(14, "two", 5000),
        ])})

        facts = self.collect(directory, maxExecutions=2)

        self.assertEqual([it["command"] for it in facts["commands"]], ["one", "two"])
        self.assertEqual(facts["dropped"], 2)
        self.assertEqual(facts["counts"], {"executions": 4, "commands": 2})

    def test_reads_a_ceiling_that_is_not_a_number_as_the_default(self):
        directory = self.workspace_with(**{"4242.ndjson": session(executed=[executed(11, "one", 2000)])})

        self.assertEqual(self.collect(directory, maxExecutions="lots")["counts"]["executions"], 1)

    def test_reads_a_session_a_monitor_is_still_appending_to(self):
        directory = self.workspace_with(**{"4242.ndjson": session(
            executed=[executed(11, "git status", 2000)],
        ) + '{"executed": {"pid": 12, "comm'})

        facts = self.collect(directory)

        self.assertEqual([it["command"] for it in facts["commands"]], ["git status"])
        self.assertEqual(facts["monitor"]["running"], True)

    def test_reads_the_sessions_directory_the_environment_names(self):
        directory = self.workspace_with(**{"4242.ndjson": session()})
        os.environ["BUILDNOTE_MONITOR_DIR"] = os.path.join(directory, "sessions")
        self.addCleanup(os.environ.pop, "BUILDNOTE_MONITOR_DIR", None)

        self.assertEqual(self.collect(directory, sessionsDir="")["monitor"]["pid"], 4242)

    def test_collects_nothing_when_no_monitor_has_recorded(self):
        facts = self.collect(self.workspace(**{"sessions/notes.txt": "not a session\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no buildnote monitor session was found", facts["reason"])
        self.assertEqual(facts["reports"], [])

    def test_collects_nothing_when_the_directory_is_not_there(self):
        self.assertEqual(self.collect(self.workspace())["source"], "none")

    def test_collects_nothing_when_a_session_names_no_build(self):
        directory = self.workspace_with(**{"4242.ndjson": '{"executed": {"pid": 1, "command": "x"}}\n'})

        self.assertIn("names the build it recorded", self.collect(directory)["reason"])


if __name__ == "__main__":
    unittest.main()
