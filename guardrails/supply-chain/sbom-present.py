#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    sbom = guardrail.facts("sbom", "no sbom collector ran")
    minimum = guardrail.number("minComponents", 1)

    if sbom.get("source") == "none":
        guardrail.violation(
            "no bill of materials",
            "The build produced no software bill of materials: %s" % sbom.get("reason", "none was found")
        )
    elif sbom["counts"]["total"] < minimum:
        guardrail.violation(
            "%d components" % sbom["counts"]["total"],
            "The bill of materials names %d components, fewer than the %d expected of a real inventory" % (
                sbom["counts"]["total"], minimum
            )
        )
