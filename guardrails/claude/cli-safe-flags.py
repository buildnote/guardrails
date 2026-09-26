#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_FLAGS = "--dangerously-skip-permissions,--allow-dangerously-skip-permissions"
CLAUDE_EXECUTABLES = ("claude", "claude.exe", "claude.cmd")


def basename(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1]


def invokes_claude(tokens):
    return any(basename(token) in CLAUDE_EXECUTABLES for token in tokens)


with Guardrail() as guardrail:
    flags = [it.strip() for it in guardrail.input("dangerousFlags", DEFAULT_FLAGS).split(",") if it.strip()]
    commands = guardrail.facts("commands")

    if commands.get("source") == "none":
        guardrail.skip(commands.get("reason") or "no commands were recorded for this build")

    invocations = []
    for executed in commands["commands"]:
        if invokes_claude(executed["command"].split()) and executed["command"] not in invocations:
            invocations.append(executed["command"])

    if not invocations:
        if commands["dropped"]:
            guardrail.skip(
                "no Claude CLI invocation was recorded, and %d executions were left out of the facts"
                % commands["dropped"]
            )
        guardrail.skip("no Claude CLI invocation was recorded for this build")

    for invocation in invocations:
        tokens = invocation.split()

        for flag in flags:
            if flag in tokens or any(token.startswith(flag + "=") for token in tokens):
                guardrail.violation(
                    invocation,
                    "Claude ran with %s, which lets it act on the repository and the runner with no approval step"
                    % flag,
                )
