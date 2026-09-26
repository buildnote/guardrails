#!/usr/bin/env python3
import re

from guardrail import Guardrail

NUMBERS = re.compile(r"\d+(?:\.\d+)*")


def numbers(version):
    found = NUMBERS.search(version or "")

    return tuple(int(part) for part in found.group(0).split(".")) if found else None


def older(version, floor):
    left, right = numbers(version), numbers(floor)

    if left is None or right is None:
        return False

    size = max(len(left), len(right))

    return left + (0,) * (size - len(left)) < right + (0,) * (size - len(right))


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_version = guardrail.input("minVersion", "18")
    nodejs = guardrail.facts("nodejs", "no Node.js project in %s" % project_dir)

    if nodejs.get("incomplete"):
        guardrail.skip(nodejs["incomplete"])

    if not nodejs["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = nodejs["declared"]
    manifest = nodejs["manifest"] or project_dir

    if not declared:
        guardrail.violation(
            manifest,
            "No Node.js version declared in %s, an .nvmrc or a .node-version file, so the runtime a build runs on "
            "is whichever one the runner happens to carry" % manifest,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Node.js %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Node.js %s)" % (source, version),
                "%s asks for Node.js %s, older than the %s expected" % (source, version, min_version),
            )
