#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    git = guardrail.facts("git")

    if not git["repository"]:
        guardrail.skip("not a git repository")

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable (shallow clone?)" % git["baseRef"])

    for commit in git["commits"]:
        if not commit["merge"]:
            continue
        guardrail.violation(
            "%s %s" % (commit["short"], commit["subject"]),
            'Commit %s is a merge commit: "%s"' % (commit["short"], commit["subject"]),
        )
