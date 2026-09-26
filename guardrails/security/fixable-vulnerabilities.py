#!/usr/bin/env python3
from guardrail import Guardrail

RANKED = ["critical", "high", "medium", "low", "info", "unknown"]

with Guardrail() as guardrail:
    scan = guardrail.facts("scan", "no scan collector ran")
    gate = guardrail.input("severity", "medium").strip().lower()
    kinds = [kind.strip() for kind in guardrail.input("kinds", "sast,sca,iac,container,secret").split(",") if kind.strip()]

    if gate not in RANKED:
        guardrail.skip("severity '%s' is not one of %s" % (gate, ", ".join(RANKED[:-1])))

    if scan.get("source") == "none":
        guardrail.skip(scan.get("reason", "no scanner report was read"))

    gated = RANKED.index(gate)

    for finding in scan.get("findings", []):
        severity = finding.get("severity", "unknown")
        fixed_in = finding.get("fixedIn")

        if not fixed_in:
            continue

        if severity not in RANKED or RANKED.index(severity) > gated:
            continue

        if finding.get("kind") not in kinds:
            continue

        package = finding.get("package") or {}
        named = package.get("name") or finding.get("path") or "the build"
        version = package.get("version")

        guardrail.violation(
            "%s %s -> %s" % (named, version or "", fixed_in),
            "%s finding %s affects %s%s and is fixed in %s, so it costs an upgrade rather than a decision"
            % (severity, finding.get("id", "finding"), named, " " + version if version else "", fixed_in),
        )

    if scan.get("dropped"):
        guardrail.log("%d findings were left out of the facts by the collector" % scan["dropped"])
