#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    git = guardrail.facts("git", "no git repository")
    markers = [it.strip() for it in guardrail.input("markers", "fixup!,squash!,amend!,WIP,wip:,TEMP,DO NOT MERGE").split(",") if it.strip()]

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable" % git["baseRef"])

    for commit in git["commits"]:
        subject = commit["subject"]
        found = [marker for marker in markers if subject.lower().startswith(marker.lower())]

        if not found:
            continue

        guardrail.violation(
            "%s %s" % (commit["short"], subject),
            "Commit %s is marked %s and was not meant to be merged: \"%s\"" % (commit["short"], found[0], subject)
        )
