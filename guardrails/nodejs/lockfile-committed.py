#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    nodejs = guardrail.facts("nodejs", "no Node.js project in %s" % project_dir)

    if nodejs.get("incomplete"):
        guardrail.skip(nodejs["incomplete"])

    if not nodejs["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = nodejs["lockfiles"]

    if not lockfiles:
        guardrail.violation(
            nodejs["manifest"] or project_dir,
            "The Node.js project in %s commits no lock file, so an install of this commit can resolve different "
            "versions than the one that was reviewed" % project_dir,
        )
    else:
        guardrail.log("locked by %s" % ", ".join(sorted(lockfiles)))
