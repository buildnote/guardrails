#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("github", "no github collector ran").get("codeowners")
    minimum = guardrail.number("minOwners", 1)
    maximum = guardrail.number("maxOwners", 5)

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]

    for rule in codeowners["rules"]:
        owners = rule["owners"]

        if not owners:
            continue

        evidence = "%s:%d %s (%d owners)" % (path, rule["line"], rule["pattern"], len(owners))

        if len(owners) < minimum:
            guardrail.violation(
                evidence,
                "%s is owned by %d, fewer than the %d expected" % (rule["pattern"], len(owners), minimum),
            )
        elif maximum and len(owners) > maximum:
            guardrail.violation(
                evidence,
                "%s is owned by %d, more than the %d a rule may name" % (rule["pattern"], len(owners), maximum),
            )
