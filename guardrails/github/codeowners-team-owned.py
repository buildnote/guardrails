#!/usr/bin/env python3
from guardrail import Guardrail


def team(owner):
    return owner.startswith("@") and "/" in owner


with Guardrail() as guardrail:
    codeowners = guardrail.facts("github", "no github collector ran").get("codeowners")
    allow_individuals = guardrail.input("allowIndividuals", "true").strip().lower() != "false"

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]

    for rule in codeowners["rules"]:
        owners = rule["owners"]

        if not owners:
            continue

        individuals = [owner for owner in owners if not team(owner)]

        if len(individuals) == len(owners):
            guardrail.violation(
                "%s:%d %s" % (path, rule["line"], rule["pattern"]),
                "%s is owned only by individuals (%s), so ownership goes stale when they move on"
                % (rule["pattern"], ", ".join(individuals)),
            )
        elif individuals and not allow_individuals:
            guardrail.violation(
                "%s:%d %s" % (path, rule["line"], rule["pattern"]),
                "%s names individuals beside its team (%s)" % (rule["pattern"], ", ".join(individuals)),
            )
