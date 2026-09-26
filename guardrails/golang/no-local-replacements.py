#!/usr/bin/env python3
import re

from guardrail import Guardrail

DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def directory(target):
    return target.startswith(".") or target.startswith("/") or DRIVE.match(target) is not None


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    golang = guardrail.facts("golang", "no Go module in %s" % project_dir)

    if golang.get("incomplete"):
        guardrail.skip(golang["incomplete"])

    if not golang["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    replaced = golang["replaced"]
    local = [it for it in replaced if directory(it["with"])]

    for replacement in local:
        name, target, source = replacement["name"], replacement["with"], replacement["source"]
        guardrail.violation(
            "%s (%s => %s)" % (source, name, target),
            "%s replaces %s with the directory %s, which the checkout does not carry, so the build only resolves on "
            "a machine that already has it" % (source, name, target),
        )

    if replaced and not local:
        guardrail.log("replaces %s, each with a module path" % ", ".join(it["name"] for it in replaced))
