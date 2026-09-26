#!/usr/bin/env python3
import fnmatch
import posixpath

from guardrail import Guardrail

DEFAULT_MODULES = "modules/*,*/modules/*"

LOCK_FILE = ".terraform.lock.hcl"


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


def at(root, name):
    return name if root == "." else posixpath.join(root, name)


with Guardrail() as guardrail:
    terraform = guardrail.facts("terraform", "no Terraform facts were collected")
    require_lockfile = guardrail.input("requireLockfile", "true").strip().lower() != "false"
    configured = [it.strip() for it in guardrail.input("modulePaths", DEFAULT_MODULES).split(",") if it.strip()]

    if terraform.get("source") == "none":
        guardrail.skip(terraform.get("reason") or "no Terraform configuration was collected")

    roots = terraform.get("roots") or []
    modules = modules_in(roots, configured)
    live = []

    for root in roots:
        if root["path"] in modules:
            guardrail.log("%s is a reusable module, which declares a range rather than a pin" % root["path"])
        elif root["unparsed"]:
            guardrail.log("%s was read from part of its configuration, so its providers are unknown" % root["path"])
        else:
            live.append(root)

    if not live:
        guardrail.skip("no live Terraform root was collected to judge")

    for root in live:
        where = root["path"]

        for provider in root["providers"]:
            if provider["pinned"]:
                continue

            constrained = (
                "constrains it to %s rather than to one exact version" % provider["version"]
                if provider["version"] else "declares no version constraint at all"
            )

            guardrail.violation(
                "%s provider %s" % (where, provider["name"]),
                "The Terraform root %s requires the provider %s and %s, so two runs of this commit can resolve different versions."
                % (where, provider["name"], constrained)
            )

        if require_lockfile and root["providers"] and not root["lockfile"]["present"]:
            guardrail.violation(
                at(where, LOCK_FILE),
                "The Terraform root %s commits no %s, so the versions and the checksums of the providers it requires are resolved fresh on every runner."
                % (where, LOCK_FILE)
            )
