#!/usr/bin/env python3
from guardrail import Guardrail

NAMED = 3

LINES_UNDER = "Line coverage is %.2f%%, under the %g%% floor: %d of the %d lines measured are never executed"

BRANCHES_UNDER = "Branch coverage is %.2f%%, under the %g%% floor: %d of the %d branches measured are never taken"

NO_LINES = "the reports measured no lines, so there is no line coverage to hold to a floor"

NO_BRANCHES = "the reports carry no branch coverage, so there are no branches to hold to a floor"


def floor(guardrail, name):
    raw = guardrail.input(name, "0").strip()

    try:
        return float(raw)
    except ValueError:
        guardrail.skip("%s '%s' is not a number" % (name, raw))


def measured(totals):
    return bool(totals) and totals.get("covered", 0) + totals.get("missed", 0) > 0


with Guardrail() as guardrail:
    coverage = guardrail.facts("coverage", "no coverage collector ran")
    min_lines = floor(guardrail, "minLines")
    min_branches = floor(guardrail, "minBranches")

    if coverage.get("source") == "none":
        guardrail.skip(coverage.get("reason", "no coverage report was read"))

    lines = coverage.get("lines")
    branches = coverage.get("branches")

    if min_lines > 0:
        if not measured(lines):
            guardrail.log(NO_LINES)
        elif lines["percent"] < min_lines:
            worst = list(coverage.get("byFile", {}))[:NAMED]

            if worst:
                guardrail.log("least covered: %s" % ", ".join(worst))

            guardrail.violation(
                "line coverage %.2f%%" % lines["percent"],
                LINES_UNDER % (
                    lines["percent"], min_lines, lines["missed"], lines["covered"] + lines["missed"]
                )
            )

    if min_branches > 0:
        if not measured(branches):
            guardrail.log(NO_BRANCHES)
        elif branches["percent"] < min_branches:
            guardrail.violation(
                "branch coverage %.2f%%" % branches["percent"],
                BRANCHES_UNDER % (
                    branches["percent"], min_branches, branches["missed"],
                    branches["covered"] + branches["missed"]
                )
            )
