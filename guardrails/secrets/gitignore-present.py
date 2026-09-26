#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    path = guardrail.input("path", ".gitignore")
    min_lines = guardrail.number("minLines", 1)
    files = guardrail.facts("files")["files"]

    described = files.get(path)

    if described is None:
        guardrail.skip("%s was not collected" % path)

    if not described["present"]:
        guardrail.violation(
            path,
            "No %s, so build output and local credential files are staged by anything that adds the tree" % path,
        )
    elif "unreadable" in described:
        guardrail.skip("could not read %s: %s" % (path, described["unreadable"]))
    elif described["nonBlankLines"] < min_lines:
        guardrail.violation(
            "%s (%d non-blank lines)" % (path, described["nonBlankLines"]),
            "%s ignores %d paths, fewer than the %d expected" % (path, described["nonBlankLines"], min_lines),
        )
