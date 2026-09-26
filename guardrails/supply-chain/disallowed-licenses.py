#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_LICENSES = "AGPL-1.0,AGPL-3.0,SSPL-1.0,BUSL-1.1,CC-BY-NC,Commons-Clause,Elastic-2.0"

with Guardrail() as guardrail:
    sbom = guardrail.facts("sbom", "no sbom collector ran")
    refused = [it.strip().lower() for it in guardrail.input("licenses", DEFAULT_LICENSES).split(",") if it.strip()]

    if sbom.get("source") == "none":
        guardrail.skip(sbom.get("reason") or "no bill of materials was read")

    if not refused:
        guardrail.skip("no licence was named as one the team refuses")

    for component in sbom.get("components", []):
        for licence in component["licenses"]:
            named = [it for it in refused if it in licence.lower()]

            if not named:
                continue

            versioned = "%s %s" % (component["name"], component["version"] or "")

            guardrail.violation(
                "%s (%s)" % (versioned.strip(), licence),
                "The component %s is licensed under %s, which the team does not ship"
                % (versioned.strip(), licence),
            )
            break

    if sbom.get("dropped"):
        guardrail.log("%d components were left out of the facts by the collector" % sbom["dropped"])
