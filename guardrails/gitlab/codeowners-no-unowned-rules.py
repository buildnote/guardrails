#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("gitlab", "no gitlab collector ran").get("codeowners")

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]

    for section in codeowners["sections"]:
        for rule in section["rules"]:
            if rule["owners"]:
                continue

            guardrail.violation(
                "%s:%d %s" % (path, rule["line"], rule["pattern"]),
                "%s line %d names no owner for %s, and the [%s] section it sits in declares no default owners, "
                "so nothing in that section owns what it matches"
                % (path, rule["line"], rule["pattern"], section["name"]),
            )
