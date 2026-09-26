#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    elixir = guardrail.facts("elixir", "no Mix project in %s" % project_dir)

    if elixir.get("incomplete"):
        guardrail.skip(elixir["incomplete"])

    if not elixir["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    direct = elixir["dependencies"]["direct"]
    from_git = [it for it in direct if it["origin"] == "git"]

    for dependency in from_git:
        guardrail.violation(
            "%s (%s)" % (dependency["name"], dependency["source"]),
            "%s takes %s from a git repository rather than from Hex, so the build compiles whatever that reference "
            "points at with no published release or checksum behind it" % (dependency["source"], dependency["name"]),
        )

    if not from_git:
        guardrail.log(
            "none of the %d dependencies read from %s comes from git; a Mix manifest is Elixir read by pattern, "
            "so a dependency added inside a condition or built by a function is not among them"
            % (len(direct), ", ".join(elixir["scanned"]))
        )
