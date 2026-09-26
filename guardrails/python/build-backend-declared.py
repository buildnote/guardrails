#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    python = guardrail.facts("python", "no Python project in %s" % project_dir)

    if python.get("incomplete"):
        guardrail.skip(python["incomplete"])

    if not python["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if python["packaging"] == "requirements":
        guardrail.skip("%s declares requirements rather than a package to build" % project_dir)

    backend = python["backend"]

    if not backend:
        guardrail.violation(
            python["manifest"] or project_dir,
            "%s declares no build backend, so building it falls back to whichever setuptools the environment "
            "carries" % (python["manifest"] or project_dir),
        )
    else:
        guardrail.log("built by %s" % backend)
