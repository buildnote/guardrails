#!/usr/bin/env python3
from guardrail import Guardrail

FAILED = "failed"

with Guardrail() as guardrail:
    tests = guardrail.facts("tests", "no tests collector ran")

    if tests.get("source") == "none":
        guardrail.skip(tests.get("reason", "no test report was read"))

    failures = tests.get("failures", [])
    totals = tests.get("totals", {})

    for case in failures:
        name = case.get("name") or "an unnamed case"
        suite = case.get("classname") or case.get("file")
        ended = "failed" if case.get("status") == FAILED else "ended in an error"

        guardrail.violation(
            "%s.%s" % (suite, name) if suite else name,
            "The test %s%s %s" % (name, " in %s" % suite if suite else "", ended)
        )

    reported = totals.get("failed", 0) + totals.get("errors", 0)

    if reported > len(failures):
        guardrail.log(
            "%d of the %d failing cases were left out of the facts by the collector"
            % (reported - len(failures), reported)
        )
