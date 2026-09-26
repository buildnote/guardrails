#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_PATHS = "AGENTS.md,CLAUDE.md,.github/copilot-instructions.md"

with Guardrail() as guardrail:
    paths = [it.strip() for it in guardrail.input("paths", DEFAULT_PATHS).split(",") if it.strip()]
    min_lines = guardrail.number("minLines", 10)
    max_lines = guardrail.number("maxLines", 500)
    files = guardrail.facts("files")["files"]

    described = [(path, files[path]) for path in paths if path in files]

    if not described:
        guardrail.skip("none of %s was collected" % ", ".join(paths))

    present = [(path, it) for path, it in described if it["present"]]

    if not present:
        guardrail.violation(
            paths[0],
            "The repository instructs no coding agent: none of %s is there" % ", ".join(paths),
        )
    else:
        path, instructions = present[0]

        if "unreadable" in instructions:
            guardrail.skip("could not read %s: %s" % (path, instructions["unreadable"]))
        elif instructions["nonBlankLines"] < min_lines:
            guardrail.violation(
                "%s (%d non-blank lines)" % (path, instructions["nonBlankLines"]),
                "Agent instructions at %s have %d non-blank lines, fewer than the %d expected"
                % (path, instructions["nonBlankLines"], min_lines),
            )
        elif max_lines and instructions["nonBlankLines"] > max_lines:
            guardrail.violation(
                "%s (%d non-blank lines)" % (path, instructions["nonBlankLines"]),
                "Agent instructions at %s have %d non-blank lines, more than the %d that will be attended to"
                % (path, instructions["nonBlankLines"], max_lines),
            )
