#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("github", "no github collector ran").get("codeowners")
    patterns = [it.strip() for it in guardrail.input("patterns", "*,**,/*").split(",") if it.strip()]

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]
    covering = [rule for rule in codeowners["rules"] if rule["pattern"] in patterns and rule["owners"]]

    if not covering:
        guardrail.violation(
            path,
            "%s declares no owned catch-all rule, so a path no rule names is owned by nobody" % path,
        )
