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


def live_roots(guardrail, terraform, configured, unknown):
    roots = terraform.get("roots") or []
    modules = modules_in(roots, configured)
    live = []

    for root in roots:
        if root["path"] in modules:
            guardrail.log("%s is a reusable module rather than a live root" % root["path"])
        elif root["unparsed"]:
            guardrail.log(unknown % root["path"])
        else:
            live.append(root)

    return live


with Guardrail() as guardrail:
    terraform = guardrail.facts("terraform", "no Terraform facts were collected")
    configured = [it.strip() for it in guardrail.input("modulePaths", DEFAULT_MODULES).split(",") if it.strip()]

    if terraform.get("source") == "none":
        guardrail.skip(terraform.get("reason") or "no Terraform configuration was collected")

    live = live_roots(
        guardrail, terraform, configured, "%s was read from part of its configuration, so its backend is unknown"
    )

    if not live:
        guardrail.skip("no live Terraform root was collected to judge")

    for root in live:
        backend = root["backend"]

        if backend["locking"]:
            continue

        guardrail.violation(
            root["path"],
            "The Terraform root %s stores state in a %s backend that declares no locking, so two applies that overlap each write a state describing only what they did"
            % (root["path"], backend["type"]),
        )
