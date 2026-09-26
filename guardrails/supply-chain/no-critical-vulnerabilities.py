#!/usr/bin/env python3
from guardrail import Guardrail

RANKED = ["critical", "high", "medium", "low", "info", "unknown"]


def named(finding):
    package = finding.get("package") or {}

    if package.get("name"):
        return "%s %s" % (package["name"], package.get("version") or "")

    return finding.get("path") or "the build"


with Guardrail() as guardrail:
    scan = guardrail.facts("scan", "no scan collector ran")
    gate = guardrail.input("severity", "critical").strip().lower()
    ignored = [it.strip() for it in guardrail.input("ignore", "").split(",") if it.strip()]

    if gate not in RANKED:
        guardrail.skip("severity '%s' is not one of %s" % (gate, ", ".join(RANKED[:-1])))

    if scan.get("source") == "none":
        guardrail.skip(scan.get("reason", "no scanner report was read"))

    gated = RANKED.index(gate)

    for finding in scan.get("findings", []):
        if finding.get("kind") != "sca":
            continue

        severity = finding.get("severity", "unknown")

        if severity not in RANKED or RANKED.index(severity) > gated:
            continue

        identifiers = [finding.get("id")] + list(finding.get("identifiers") or [])

        if any(identifier in ignored for identifier in identifiers if identifier):
            guardrail.log("%s is on the ignore list" % finding.get("id"))
            continue

        fixed = finding.get("fixedIn")

        guardrail.violation(
            "%s %s" % (finding.get("id", "finding"), named(finding).strip()),
            "%s %s affects %s%s" % (
                severity,
                finding.get("id", "finding"),
                named(finding).strip(),
                ", fixed in %s" % fixed if fixed else ", with no fixed version named"
            )
        )
