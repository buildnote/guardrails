#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    sbom = guardrail.facts("sbom", "no sbom collector ran")
    accepted = [it.strip().lower() for it in guardrail.input("formats", "cyclonedx,spdx").split(",") if it.strip()]
    needs_version = guardrail.input("requireSpecVersion", "true").strip().lower() != "false"

    if sbom.get("source") == "none":
        guardrail.skip(sbom.get("reason") or "no bill of materials was read")

    for report in sbom["reports"]:
        if report["format"].lower() not in accepted:
            guardrail.violation(
                "%s (%s)" % (report["path"], report["format"]),
                "The bill of materials at %s is written as %s rather than as one of %s, so what reads it years "
                "from now has to be the tool that wrote it"
                % (report["path"], report["format"], ", ".join(accepted)),
            )

    if needs_version and sbom["specVersion"] is None:
        guardrail.violation(
            sbom["reports"][0]["path"] if sbom["reports"] else "the bill of materials",
            "The bill of materials declares no specification version, so nothing can tell which fields it was "
            "allowed to leave out",
        )
