#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    nodejs = guardrail.facts("nodejs", "no Node.js project in %s" % project_dir)

    if nodejs.get("incomplete"):
        guardrail.skip(nodejs["incomplete"])

    if not nodejs["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = sorted(nodejs["lockfiles"])

    if len(lockfiles) > 1:
        guardrail.violation(
            ", ".join(lockfiles),
            "The Node.js project in %s commits %d lock files (%s), so two package managers each believe they own "
            "the tree and which versions are installed depends on which one is run"
            % (project_dir, len(lockfiles), ", ".join(lockfiles)),
        )
