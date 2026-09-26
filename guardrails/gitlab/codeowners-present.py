#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("gitlab", "no gitlab collector ran").get("codeowners")

    if codeowners is None:
        guardrail.violation(
            "no CODEOWNERS",
            "The project declares no code owners: no CODEOWNERS file at any location GitLab reads one from",
        )
    elif not any(section["rules"] for section in codeowners["sections"]):
        guardrail.violation(
            codeowners["path"],
            "%s declares no rule in any section, so it names no owner for anything" % codeowners["path"],
        )
