#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail

MATCHES = ("any", "all")


def basename(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1]


def named(value):
    return [it.strip() for it in value.split(",") if it.strip()]


def invoked(tokens, executables):
    for token in tokens:
        if basename(token) in executables:
            return basename(token)

    return None


def carries(tokens, argument):
    return any(
        token == argument or token.startswith(argument + "=") or fnmatch.fnmatchcase(token, argument)
        for token in tokens
    )


with Guardrail() as guardrail:
    executables = named(guardrail.input("command"))
    arguments = named(guardrail.input("arguments"))
    match = guardrail.input("match", "any")
    reason = guardrail.input("reason")

    if not executables:
        guardrail.skip("no command was named to look for")

    if match not in MATCHES:
        guardrail.skip("match '%s' is neither any nor all" % match)

    commands = guardrail.facts("commands")

    if commands.get("source") == "none":
        guardrail.skip(commands.get("reason") or "no commands were recorded for this build")

    invocations = []
    for executed in commands["commands"]:
        if invoked(executed["command"].split(), executables) and executed["command"] not in invocations:
            invocations.append(executed["command"])

    wanted = " or ".join(executables)

    if not invocations:
        if commands["dropped"]:
            guardrail.skip(
                "no %s invocation was recorded, and %d executions were left out of the facts"
                % (wanted, commands["dropped"])
            )
        guardrail.skip("no %s invocation was recorded for this build" % wanted)

    for invocation in invocations:
        tokens = invocation.split()
        carried = [argument for argument in arguments if carries(tokens, argument)]
        forbidden = not arguments or (len(carried) == len(arguments) if match == "all" else bool(carried))

        if not forbidden:
            continue

        detail = " with %s" % ", ".join(carried) if carried else ""

        guardrail.violation(
            invocation,
            reason
            or "%s ran%s, which this repository does not allow the build to run"
            % (invoked(tokens, executables), detail),
        )
