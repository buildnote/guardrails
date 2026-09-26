#!/usr/bin/env python3
from guardrail import Guardrail

RANKED = ["critical", "high", "medium", "low", "info", "unknown"]


def located(finding):
    path = finding.get("path") or "the checkout"
    line = finding.get("line")

    return "%s:%s" % (path, line) if line else path


with Guardrail() as guardrail:
    secrets = guardrail.facts("secrets", "no secrets collector ran")
    gate = guardrail.input("severity", "high").strip().lower()
    accepted = [rule.strip() for rule in guardrail.input("ignore", "").split(",") if rule.strip()]

    if gate not in RANKED:
        guardrail.skip("severity '%s' is not one of %s" % (gate, ", ".join(RANKED[:-1])))

    if secrets.get("source") == "none":
        guardrail.skip(secrets.get("reason", "nothing scanned this checkout for secrets"))

    gated = RANKED.index(gate)

    for finding in secrets.get("findings", []):
        severity = finding.get("severity", "unknown")

        if severity not in RANKED or RANKED.index(severity) > gated:
            continue

        rule = finding.get("id") or "secret"

        if rule in accepted:
            continue

        at = located(finding)

        guardrail.violation(
            "%s %s" % (at, rule),
            "%s severity credential matching %s is in the checkout at %s. "
            "Rotate it, take it out of the repository and read it from the environment instead."
            % (severity, rule, at)
        )

    if secrets.get("dropped"):
        guardrail.log("%d findings were left out of the facts by the collector" % secrets["dropped"])
