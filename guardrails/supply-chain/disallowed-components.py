#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    sbom = guardrail.facts("sbom", "no sbom collector ran")
    refused = [it.strip().lower() for it in guardrail.input("components", "").split(",") if it.strip()]

    if not refused:
        guardrail.skip("no component was named as one the team refuses")

    if sbom.get("source") == "none":
        guardrail.skip(sbom.get("reason") or "no bill of materials was read")

    for component in sbom.get("components", []):
        identity = [component["name"].lower(), (component["purl"] or "").lower()]
        named = [it for it in refused if any(it in part for part in identity if part)]

        if not named:
            continue

        versioned = ("%s %s" % (component["name"], component["version"] or "")).strip()

        guardrail.violation(
            versioned,
            "The artifact ships %s, which the team has decided against" % versioned,
        )

    if sbom.get("dropped"):
        guardrail.log("%d components were left out of the facts by the collector" % sbom["dropped"])
