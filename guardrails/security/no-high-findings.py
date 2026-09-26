#!/usr/bin/env python3
from guardrail import Guardrail

RANKED = ["critical", "high", "medium", "low", "info", "unknown"]

with Guardrail() as guardrail:
    scan = guardrail.facts("scan", "no scan collector ran")
    gate = guardrail.input("severity", "high").strip().lower()
    kinds = [kind.strip() for kind in guardrail.input("kinds", "sast,iac,container,secret").split(",") if kind.strip()]

    if gate not in RANKED:
        guardrail.skip("severity '%s' is not one of %s" % (gate, ", ".join(RANKED[:-1])))

    if scan.get("source") == "none":
        guardrail.skip(scan.get("reason", "no scanner report was read"))

    gated = RANKED.index(gate)

    for finding in scan.get("findings", []):
        severity = finding.get("severity", "unknown")

        if severity not in RANKED or RANKED.index(severity) > gated:
            continue

        if finding.get("kind") not in kinds:
            continue

        located = finding.get("path") or "the build"
        line = finding.get("line")

        guardrail.violation(
            "%s:%s %s" % (located, line if line else "", finding.get("id", "finding")),
            "%s finding %s in %s: %s" % (
                severity, finding.get("id", "finding"), located, finding.get("message", "")
            )
        )

    if scan.get("dropped"):
        guardrail.log("%d findings were left out of the facts by the collector" % scan["dropped"])
