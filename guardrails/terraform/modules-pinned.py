#!/usr/bin/env python3
import re

from guardrail import Guardrail

SHA = re.compile(r"^[0-9a-f]{40}$")


def ref_in(source):
    for part in source.split("?", 1)[-1].split("&"):
        name, _, value = part.partition("=")
        if name == "ref":
            return value

    return None


with Guardrail() as guardrail:
    terraform = guardrail.facts("terraform", "no Terraform facts were collected")
    allow_movable = guardrail.input("allowMovableRefs", "false").strip().lower() == "true"

    if terraform.get("source") == "none":
        guardrail.skip(terraform.get("reason") or "no Terraform configuration was collected")

    roots = terraform.get("roots") or []
    declared = [(root["path"], module) for root in roots for module in root["modules"]]

    if not declared:
        guardrail.skip("no Terraform root declares a module")

    for where, module in declared:
        named = "%s in %s" % (module["name"], where)

        if module["local"]:
            continue

        if module["registry"]:
            if not module["version"]:
                guardrail.violation(
                    named,
                    "The module %s is taken from the registry as %s and names no version, so the same commit can build from different code"
                    % (named, module["source"]),
                )
        elif module["git"]:
            ref = ref_in(module["source"] or "")

            if ref is None:
                guardrail.violation(
                    named,
                    "The module %s is taken from %s with no ref, so it builds from whatever the default branch is at apply time"
                    % (named, module["source"]),
                )
            elif not allow_movable and not SHA.match(ref):
                guardrail.violation(
                    named,
                    "The module %s is taken from %s at ref %s, which is a tag or a branch and can be moved out from under the pin"
                    % (named, module["source"], ref),
                )
        elif module["source"] is None:
            guardrail.log("%s takes an interpolated source, which cannot be read as a pin" % named)
