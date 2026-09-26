#!/usr/bin/env python3
from guardrail import Guardrail


def counted(count, noun):
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


with Guardrail() as guardrail:
    tests = guardrail.facts("tests", "no tests collector ran")
    minimum = guardrail.number("minTests", 1)

    if tests.get("source") == "none":
        guardrail.violation(
            "no test report",
            "The build produced no test report: %s" % tests.get("reason", "none was found")
        )
    else:
        total = tests.get("totals", {}).get("tests", 0)

        if total < minimum:
            guardrail.violation(
                counted(total, "test"),
                "The build published %s naming %s in total, fewer than the %d this guardrail asks for" % (
                    counted(tests.get("suites", 0), "test report"), counted(total, "case"), minimum
                )
            )
