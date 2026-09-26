#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail

with Guardrail() as guardrail:
    git = guardrail.facts("git", "no git repository")
    limit = guardrail.number("maxLines", 500)
    ignored = [it.strip() for it in guardrail.input("ignore", "").split(",") if it.strip()]

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable" % git["baseRef"])

    counted = [
        change for change in git["changes"]
        if not any(fnmatch.fnmatch(change["path"], pattern) for pattern in ignored)
    ]

    added = sum(change["added"] or 0 for change in counted)
    deleted = sum(change["deleted"] or 0 for change in counted)

    if added + deleted > limit:
        guardrail.violation(
            "%d lines changed" % (added + deleted),
            "This change adds %d lines and removes %d, over the %d a reviewer is asked to read at once"
            % (added, deleted, limit)
        )
