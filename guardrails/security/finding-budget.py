#!/usr/bin/env python3
from guardrail import Guardrail

RANKED = ["critical", "high", "medium", "low", "info", "unknown"]

with Guardrail() as guardrail:
    scan = guardrail.facts("scan", "no scan collector ran")
    gate = guardrail.input("severity", "medium").strip().lower()
    budget = guardrail.number("budget", 25)
    kinds = [kind.strip() for kind in guardrail.input("kinds", "sast,sca,iac,container,secret").split(",") if kind.strip()]

    if gate not in RANKED:
        guardrail.skip("severity '%s' is not one of %s" % (gate, ", ".join(RANKED[:-1])))

    if scan.get("source") == "none":
        guardrail.skip(scan.get("reason", "no scanner report was read"))

    gated = RANKED.index(gate)
    counted = [
        finding for finding in scan.get("findings", [])
        if finding.get("severity") in RANKED
        and RANKED.index(finding["severity"]) <= gated
        and finding.get("kind") in kinds
    ]

    if scan.get("dropped"):
        guardrail.log("%d findings were left out of the facts by the collector" % scan["dropped"])

    if len(counted) > budget:
        guardrail.violation(
            "%d findings at or above %s" % (len(counted), gate),
            "The build carries %d findings at or above %s, more than the %d the team budgets for, which is past "
            "the point where the report is triaged rather than skimmed" % (len(counted), gate, budget),
        )
