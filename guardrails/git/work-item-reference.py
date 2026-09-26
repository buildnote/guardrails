#!/usr/bin/env python3
import re

from guardrail import Guardrail

with Guardrail() as guardrail:
    git = guardrail.facts("git", "no git repository")
    configured = guardrail.input("pattern", "[A-Z][A-Z0-9]+-[0-9]+")
    allow_branch = guardrail.input("allowBranch", "true").strip().lower() != "false"

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable" % git["baseRef"])

    try:
        pattern = re.compile(configured)
    except re.error as invalid:
        guardrail.skip("pattern '%s' is not a regular expression: %s" % (configured, invalid))

    branch = git["head"]["branch"] or ""

    if allow_branch and pattern.search(branch):
        guardrail.log("branch %s references a work item, so its commits are covered" % branch)
    else:
        for commit in git["commits"]:
            if pattern.search(commit["message"]):
                continue

            guardrail.violation(
                "%s %s" % (commit["short"], commit["subject"]),
                "Commit %s references no work item: \"%s\"" % (commit["short"], commit["subject"])
            )
