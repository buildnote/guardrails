#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    path = guardrail.input("path", "README.md")
    min_lines = guardrail.number("minLines", 10)
    files = guardrail.facts("files")["files"]

    described = files.get(path)

    if described is None:
        guardrail.skip("%s was not collected" % path)

    if not described["present"]:
        guardrail.violation(path, "No README at %s" % path)
    elif "unreadable" in described:
        guardrail.skip("could not read %s: %s" % (path, described["unreadable"]))
    elif described["nonBlankLines"] < min_lines:
        guardrail.violation(
            "%s (%d non-blank lines)" % (path, described["nonBlankLines"]),
            "README at %s has %d non-blank lines, fewer than the %d expected"
            % (path, described["nonBlankLines"], min_lines),
        )
