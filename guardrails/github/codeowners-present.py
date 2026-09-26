#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("github", "no github collector ran").get("codeowners")

    if codeowners is None:
        guardrail.violation(
            "no CODEOWNERS",
            "The repository declares no code owners: no CODEOWNERS file at any location GitHub reads one from",
        )
    elif not codeowners.get("rules"):
        guardrail.violation(
            codeowners["path"],
            "%s declares no rules, so it names no owner for anything" % codeowners["path"],
        )
