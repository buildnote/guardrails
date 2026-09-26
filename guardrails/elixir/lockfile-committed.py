#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    elixir = guardrail.facts("elixir", "no Mix project in %s" % project_dir)

    if elixir.get("incomplete"):
        guardrail.skip(elixir["incomplete"])

    if not elixir["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = elixir["lockfiles"]

    if not lockfiles:
        guardrail.violation(
            elixir["manifest"] or project_dir,
            "The Mix project in %s commits no mix.lock, so a fetch of this commit resolves whatever Hex serves that "
            "day and has no checksum to verify it against" % project_dir,
        )
    else:
        guardrail.log("locked by %s" % ", ".join(sorted(lockfiles)))
