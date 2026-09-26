#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail

with Guardrail() as guardrail:
    git = guardrail.facts("git", "no git repository")
    limit = guardrail.number("maxFiles", 50)
    ignored = [it.strip() for it in guardrail.input("ignore", "").split(",") if it.strip()]

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable" % git["baseRef"])

    counted = [
        path for path in git["changedFiles"]
        if not any(fnmatch.fnmatch(path, pattern) for pattern in ignored)
    ]

    if len(counted) > limit:
        guardrail.violation(
            "%d files changed" % len(counted),
            "This change touches %d files, over the %d a reviewer is asked to hold at once" % (len(counted), limit)
        )
