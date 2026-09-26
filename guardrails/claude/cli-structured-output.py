#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_FORMATS = "json,stream-json"
CLAUDE_EXECUTABLES = ("claude", "claude.exe", "claude.cmd")
HEADLESS_FLAGS = ("-p", "--print")
OUTPUT_FORMAT = "--output-format"


def basename(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1]


def invokes_claude(tokens):
    return any(basename(token) in CLAUDE_EXECUTABLES for token in tokens)


def headless(tokens):
    return any(token in HEADLESS_FLAGS for token in tokens)


def structured(tokens, formats):
    for index, token in enumerate(tokens):
        if token.startswith(OUTPUT_FORMAT + "="):
            return token.split("=", 1)[1] in formats
        if token == OUTPUT_FORMAT:
            return index + 1 < len(tokens) and tokens[index + 1] in formats

    return False


with Guardrail() as guardrail:
    formats = [it.strip() for it in guardrail.input("formats", DEFAULT_FORMATS).split(",") if it.strip()]
    commands = guardrail.facts("commands")

    if commands.get("source") == "none":
        guardrail.skip(commands.get("reason") or "no commands were recorded for this build")

    invocations = []
    for executed in commands["commands"]:
        tokens = executed["command"].split()

        if invokes_claude(tokens) and headless(tokens) and executed["command"] not in invocations:
            invocations.append(executed["command"])

    if not invocations:
        if commands["dropped"]:
            guardrail.skip(
                "no headless Claude CLI invocation was recorded, and %d executions were left out of the facts"
                % commands["dropped"]
            )
        guardrail.skip("no headless Claude CLI invocation was recorded for this build")

    for invocation in invocations:
        if not structured(invocation.split(), formats):
            guardrail.violation(
                invocation,
                "Claude ran headless without %s %s, so whatever read its answer read prose rather than a document"
                % (OUTPUT_FORMAT, " or ".join(formats)),
            )
