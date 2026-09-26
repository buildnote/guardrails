#!/usr/bin/env python3
from guardrail import Guardrail


def group(owner):
    return owner.startswith("@") and "/" in owner


with Guardrail() as guardrail:
    codeowners = guardrail.facts("gitlab", "no gitlab collector ran").get("codeowners")
    allow_individuals = guardrail.input("allowIndividuals", "true").strip().lower() != "false"

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]

    for section in codeowners["sections"]:
        for rule in section["rules"]:
            owners = rule["owners"]

            if not owners:
                continue

            individuals = [owner for owner in owners if not group(owner)]
            where = " inherited from [%s]" % section["name"] if rule["inherited"] else ""
            evidence = "%s:%d %s" % (path, rule["line"], rule["pattern"])

            if len(individuals) == len(owners):
                guardrail.violation(
                    evidence,
                    "%s is owned only by individuals (%s)%s, so ownership goes stale when they move on"
                    % (rule["pattern"], ", ".join(individuals), where),
                )
            elif individuals and not allow_individuals:
                guardrail.violation(
                    evidence,
                    "%s names individuals beside its group (%s)%s"
                    % (rule["pattern"], ", ".join(individuals), where),
                )
