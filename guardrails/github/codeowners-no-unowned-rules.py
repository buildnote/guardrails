#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("github", "no github collector ran").get("codeowners")

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]

    for rule in codeowners["rules"]:
        if rule["owners"]:
            continue

        guardrail.violation(
            "%s:%d %s" % (path, rule["line"], rule["pattern"]),
            "%s line %d names no owner for %s, which removes ownership from everything it matches"
            % (path, rule["line"], rule["pattern"]),
        )
