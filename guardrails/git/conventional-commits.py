#!/usr/bin/env python3
import re

from guardrail import Guardrail

BREAKING_FOOTER = re.compile(r"^(breaking[ -]change)[ \t]*:(.*)$", re.IGNORECASE)
UPPERCASE_BREAKING = ("BREAKING CHANGE", "BREAKING-CHANGE")

with Guardrail() as guardrail:
    types = guardrail.input("types", "feat|fix|chore|refactor|test|docs|build|ci|perf|style|revert")
    git = guardrail.facts("git")

    if not git["repository"]:
        guardrail.skip("not a git repository")

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable (shallow clone?)" % git["baseRef"])

    header = re.compile(r"^(%s)(\(([^)]*)\))?(!)?:(.*)$" % types)

    def problem(lines):
        match = header.match(lines[0])
        if match is None:
            return "does not follow Conventional Commits"

        scope = match.group(3)
        if scope is not None and not scope.strip():
            return "declares an empty scope"

        described = match.group(5)
        if not described.startswith(" "):
            return "is missing the space after the colon"
        if not described.strip():
            return "has no description after the colon"

        if len(lines) > 1 and lines[1].strip():
            return "does not leave a blank line between the description and the body"

        for line in lines[1:]:
            footer = BREAKING_FOOTER.match(line)
            if footer is None:
                continue
            token, description = footer.group(1), footer.group(2)
            if token not in UPPERCASE_BREAKING:
                return 'writes the breaking change footer as "%s" rather than BREAKING CHANGE' % token
            if not description.strip():
                return "has a BREAKING CHANGE footer with no description"

        return None

    for commit in git["commits"]:
        if commit["merge"]:
            continue
        lines = commit["message"].rstrip("\n").split("\n")
        failure = problem(lines)
        if failure is None:
            continue
        guardrail.violation(
            "%s %s" % (commit["short"], lines[0]),
            'Commit %s %s: "%s"' % (commit["short"], failure, lines[0]),
        )
