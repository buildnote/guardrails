#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    sbom = guardrail.facts("sbom", "no sbom collector ran")
    min_percent = guardrail.number("minPercent", 95)

    if sbom.get("source") == "none":
        guardrail.skip(sbom.get("reason") or "no bill of materials was read")

    counts = sbom["counts"]

    if not counts["total"]:
        guardrail.skip("the bill of materials lists no components")

    percent = 100.0 * counts["licensed"] / counts["total"]

    if percent < min_percent:
        unlicensed = [it["name"] for it in sbom.get("components", []) if not it["licenses"]]

        if unlicensed:
            guardrail.log("named no licence: %s" % ", ".join(sorted(unlicensed)[:10]))

        guardrail.violation(
            "%d of %d components licensed" % (counts["licensed"], counts["total"]),
            "The bill of materials names a licence for %.1f%% of its components, below the %d%% expected, "
            "so what the artifact may be distributed under cannot be answered for %d of them"
            % (percent, min_percent, counts["unlicensed"]),
        )
