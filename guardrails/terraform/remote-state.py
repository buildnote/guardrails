#!/usr/bin/env python3
import fnmatch
import posixpath

from guardrail import Guardrail

DEFAULT_MODULES = "modules/*,*/modules/*"


def resolved(root, source):
    joined = source if root == "." else posixpath.join(root, source)

    return posixpath.normpath(joined).strip("/") or "."


def modules_in(roots, configured):
    found = set()

    for root in roots:
        if any(fnmatch.fnmatch(root["path"], pattern) for pattern in configured):
            found.add(root["path"])

        for module in root["modules"]:
            if module["local"] and module["source"]:
                found.add(resolved(root["path"], module["source"]))

    return found


with Guardrail() as guardrail:
    terraform = guardrail.facts("terraform", "no Terraform facts were collected")
    check_state = guardrail.input("checkStateFiles", "true").strip().lower() != "false"
    configured = [it.strip() for it in guardrail.input("modulePaths", DEFAULT_MODULES).split(",") if it.strip()]

    if terraform.get("source") == "none":
        guardrail.skip(terraform.get("reason") or "no Terraform configuration was collected")

    roots = terraform.get("roots") or []
    modules = modules_in(roots, configured)

    for root in roots:
        where = root["path"]

        if where in modules:
            guardrail.log("%s is a reusable module rather than a live root" % where)
            continue

        if root["unparsed"]:
            guardrail.log("%s was read from part of its configuration, so its backend is unknown" % where)
            continue

        if root["backend"]["type"] == "local":
            guardrail.violation(
                where,
                "The Terraform root %s declares no remote backend, so its state is written to a local file that only the machine running the apply has."
                % where
            )

    if check_state:
        for state in terraform.get("stateFiles") or []:
            guardrail.violation(
                state["path"],
                "The Terraform state file %s is present in the working tree, and state records every attribute of every resource, the sensitive ones included."
                % state["path"]
            )
