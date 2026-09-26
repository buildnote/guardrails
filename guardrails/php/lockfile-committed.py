#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    php = guardrail.facts("php", "no Composer project in %s" % project_dir)

    if php.get("incomplete"):
        guardrail.skip(php["incomplete"])

    if not php["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = php["lockfiles"]

    if not lockfiles:
        guardrail.violation(
            php["manifest"] or project_dir,
            "The Composer project in %s commits no lock file, so an install of this commit can resolve different "
            "versions than the one that was reviewed" % project_dir,
        )
    else:
        guardrail.log("locked by %s" % ", ".join(sorted(lockfiles)))
