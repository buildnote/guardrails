#!/usr/bin/env python3
import json
import os
import tempfile

from guardrail import Collector, modified, slashed

SESSIONS_DIRECTORY = "buildnote-monitor"
SESSION_EXTENSION = ".ndjson"
MAX_COMMAND_LENGTH = 2000
DEFAULT_MAX_EXECUTIONS = 1000
TAIL_BYTES = 4096


def sessions_in(directory):
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []

    return [os.path.join(directory, name) for name in names if name.endswith(SESSION_EXTENSION)]


# The CLI resolves the directory the monitor records in and hands it over, so both halves agree rather than each
# reading a temporary directory the other may not agree on: a JVM on Linux reads java.io.tmpdir as /tmp whatever
# TMPDIR says. The fallback is for running this collector by hand.
def directory_of(named):
    return named or os.environ.get("BUILDNOTE_MONITOR_DIR", "") \
        or os.path.join(tempfile.gettempdir(), SESSIONS_DIRECTORY)


# A monitor appends to its session while this collector reads it, so the last line can be half written.
def records(path):
    try:
        handle = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return

    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                return


def elapsed(started, completed):
    if started is None or completed is None:
        return None

    return max(0, completed - started)


def header_of(path):
    for record in records(path):
        return record.get("session")

    return None


def closing_of(path):
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - TAIL_BYTES))
            tail = handle.read().decode("utf-8", "replace")
    except OSError:
        return None

    for line in reversed(tail.splitlines()):
        try:
            record = json.loads(line)
        except ValueError:
            continue

        return record.get("closedAt")

    return None


def selected(paths, build):
    described = [(path, header_of(path)) for path in paths]
    described = [(path, header) for path, header in described if header]

    if not described:
        return None, None, None

    matching = [it for it in described if build and it[1].get("build") == build]

    if matching:
        path, header = max(matching, key=lambda it: it[1].get("startedAt") or 0)
        return path, header, "build"

    path, header = max(described, key=lambda it: (closing_of(it[0]) is None, it[1].get("startedAt") or 0))
    return path, header, "recent"


with Collector() as collector:
    looked_in = directory_of(collector.input("sessionsDir", ""))

    try:
        max_executions = int(collector.input("maxExecutions", str(DEFAULT_MAX_EXECUTIONS)))
    except ValueError:
        max_executions = DEFAULT_MAX_EXECUTIONS

    sessions = sessions_in(looked_in)

    if not sessions:
        collector.empty("no buildnote monitor session was found in %s" % slashed(looked_in))

    session, header, matched = selected(sessions, os.environ.get("BUILDNOTE_BUILD", ""))

    if not session:
        collector.empty("no buildnote monitor session in %s names the build it recorded" % slashed(looked_in))

    commands = []
    running = {}
    executions = 0
    dropped = 0
    closed_at = None

    for record in records(session):
        if "executed" in record:
            executed = record["executed"]
            executions += 1

            if len(commands) >= max_executions:
                dropped += 1
                running.pop(executed.get("pid"), None)
                continue

            running[executed.get("pid")] = len(commands)
            commands.append({
                "command": (executed.get("command") or "")[:MAX_COMMAND_LENGTH],
                "pid": executed.get("pid"),
                "startedAt": executed.get("startedAt"),
                "durationMs": None,
                "exitCode": None,
            })
        elif "exited" in record:
            exited = record["exited"]
            index = running.pop(exited.get("pid"), None)

            if index is not None:
                commands[index]["durationMs"] = elapsed(commands[index]["startedAt"], exited.get("completedAt"))
                commands[index]["exitCode"] = exited.get("exitCode")
        elif "closedAt" in record:
            closed_at = record["closedAt"]

    collector.sourced("report", [{
        "path": slashed(os.path.abspath(session)),
        "modified": modified(session),
        "format": "monitor-session",
    }])

    collector.facts["monitor"] = {
        "running": closed_at is None,
        "matched": matched,
        "sessions": len(sessions),
        "pid": header.get("pid"),
        "startedAt": header.get("startedAt"),
        "closedAt": closed_at,
        "build": header.get("build"),
        "module": header.get("module"),
        "command": header.get("command"),
    }
    collector.facts["commands"] = commands
    collector.facts["counts"] = {
        "executions": executions,
        "commands": len(set(it["command"] for it in commands)),
    }
    collector.facts["dropped"] = dropped
