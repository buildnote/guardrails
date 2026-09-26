#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    minimum = guardrail.number("minLockfiles", 1)
    gradle = guardrail.facts("gradle", "no Gradle build in %s" % project_dir)

    if not gradle["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    lockfiles = gradle["lockfiles"]

    if len(lockfiles) < minimum:
        guardrail.violation(
            "%d lock files" % len(lockfiles),
            "The Gradle build in %s commits %d dependency lock files, fewer than the %d expected, so a rebuild "
            "of this commit can resolve different versions than the build that was reviewed"
            % (project_dir, len(lockfiles), minimum),
        )
    else:
        guardrail.log("locked by %s" % ", ".join(sorted(lockfiles)[:10]))
