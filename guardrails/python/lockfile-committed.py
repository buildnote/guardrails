#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    python = guardrail.facts("python", "no Python project in %s" % project_dir)

    if python.get("incomplete"):
        guardrail.skip(python["incomplete"])

    if not python["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = python["lockfiles"]

    if not lockfiles:
        guardrail.violation(
            python["manifest"] or project_dir,
            "The Python project in %s commits no lock file, so an install of this commit can resolve different "
            "versions than the one that was reviewed" % project_dir,
        )
    else:
        guardrail.log("locked by %s" % ", ".join(sorted(lockfiles)))
