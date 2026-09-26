#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    golang = guardrail.facts("golang", "no Go module in %s" % project_dir)

    if golang.get("incomplete"):
        guardrail.skip(golang["incomplete"])

    if not golang["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = golang["lockfiles"]

    if not lockfiles:
        guardrail.violation(
            golang["manifest"] or project_dir,
            "The Go module in %s commits no go.sum, so nothing verifies that the modules a build downloads are the "
            "ones this commit resolved" % project_dir,
        )
    else:
        guardrail.log("checksummed by %s" % ", ".join(sorted(lockfiles)))
