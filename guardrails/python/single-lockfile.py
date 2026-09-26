#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    python = guardrail.facts("python", "no Python project in %s" % project_dir)

    if python.get("incomplete"):
        guardrail.skip(python["incomplete"])

    if not python["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = sorted(python["lockfiles"])

    if len(lockfiles) > 1:
        guardrail.violation(
            ", ".join(lockfiles),
            "The Python project in %s commits %d lock files (%s), so which versions are installed depends on which "
            "installer is run" % (project_dir, len(lockfiles), ", ".join(lockfiles)),
        )
