#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    scan = guardrail.facts("scan", "no scan collector ran")

    if scan.get("source") == "none":
        guardrail.violation(
            "no scanner report",
            "The build produced no security scan report: %s" % scan.get("reason", "none was found")
        )
