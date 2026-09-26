#!/usr/bin/env python3
from guardrail import Guardrail

RANKED = ["critical", "high", "medium", "low", "info", "unknown"]

with Guardrail() as guardrail:
    docker = guardrail.facts("docker", "no Docker facts were collected")
    gate = guardrail.input("severity", "high").strip().lower()
    ignored = [it.strip() for it in guardrail.input("ignore", "").split(",") if it.strip()]

    if gate not in RANKED:
        guardrail.skip("severity '%s' is not one of %s" % (gate, ", ".join(RANKED[:-1])))

    if docker.get("source") == "none":
        guardrail.skip(docker.get("reason") or "no Dockerfile lint report was read")

    gated = RANKED.index(gate)

    for finding in docker.get("lint", {}).get("findings", []):
        rule = finding.get("id") or "finding"
        severity = finding.get("severity") or "unknown"

        if rule in ignored:
            continue

        if severity not in RANKED or RANKED.index(severity) > gated:
            continue

        located = finding.get("path") or "the build"
        line = finding.get("line")

        guardrail.violation(
            "%s:%s %s" % (located, line if line else "", rule),
            "%s lint finding %s in %s: %s" % (severity, rule, located, finding.get("message", "")),
        )

    if docker.get("lint", {}).get("dropped"):
        guardrail.log("%d findings were left out of the facts by the collector" % docker["lint"]["dropped"])
