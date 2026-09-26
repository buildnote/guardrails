#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    rust = guardrail.facts("rust", "no Cargo build in %s" % project_dir)

    if rust.get("incomplete"):
        guardrail.skip(rust["incomplete"])

    if not rust["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = rust["lockfiles"]

    if not lockfiles:
        guardrail.violation(
            rust["manifest"] or project_dir,
            "The Cargo build in %s commits no lock file, so a rebuild of this commit can resolve different crate "
            "versions than the build that was reviewed" % project_dir,
        )
    else:
        guardrail.log("locked by %s" % ", ".join(sorted(lockfiles)))
