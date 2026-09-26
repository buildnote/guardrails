#!/usr/bin/env python3
from guardrail import Guardrail

NAMED = 10


def counted(count, noun):
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


with Guardrail() as guardrail:
    tests = guardrail.facts("tests", "no tests collector ran")
    budget = guardrail.number("maxSkipped", 0)

    if tests.get("source") == "none":
        guardrail.skip(tests.get("reason", "no test report was read"))

    skipped = tests.get("totals", {}).get("skipped", 0)

    if skipped > budget:
        named = [case.get("name") or "an unnamed case" for case in tests.get("skipped", [])][:NAMED]

        if named:
            guardrail.log("skipped: %s" % ", ".join(named))

        guardrail.violation(
            "%s skipped" % counted(skipped, "test"),
            "%s skipped, over the budget of %d this guardrail is configured with" % (
                counted(skipped, "test"), budget
            )
        )
