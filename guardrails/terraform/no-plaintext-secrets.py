#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail

DEFAULT_PATTERNS = "*SECRET*,*TOKEN*,*PASSWORD*,*KEY*,*CREDENTIAL*"


def matching(name, patterns):
    for pattern in patterns:
        if fnmatch.fnmatchcase(name.upper(), pattern):
            return pattern

    return None


with Guardrail() as guardrail:
    terraform = guardrail.facts("terraform", "no Terraform facts were collected")
    patterns = [it.strip().upper() for it in guardrail.input("patterns", DEFAULT_PATTERNS).split(",") if it.strip()]

    if terraform.get("source") == "none":
        guardrail.skip(terraform.get("reason") or "no Terraform configuration was collected")

    roots = terraform.get("roots") or []

    if not roots:
        guardrail.skip("no Terraform root was collected to judge")

    if not patterns:
        guardrail.skip("no patterns are configured, so no name can be judged")

    for root in roots:
        where = root["path"]

        for variable in root["variables"]:
            name = variable["name"] or ""
            pattern = matching(name, patterns)

            if pattern is None or variable["sensitive"]:
                continue

            guardrail.violation(
                "%s:%s" % (where, name),
                "The Terraform root %s declares the variable %s, whose name matches %s, without sensitive = true, so its value is printed in every plan that reads it."
                % (where, name, pattern)
            )
