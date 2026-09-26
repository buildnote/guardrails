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
    min_version = guardrail.input("minVersion", "1.21")
    golang = guardrail.facts("golang", "no Go module in %s" % project_dir)

    if golang.get("incomplete"):
        guardrail.skip(golang["incomplete"])

    if not golang["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = golang["declared"]
    read = ", ".join(golang["sources"]) or project_dir

    if not declared:
        guardrail.violation(
            read,
            "No Go version declared in %s, so the language version the code is compiled against is whichever one "
            "the runner's toolchain defaults to" % read,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Go %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Go %s)" % (source, version),
                "%s asks for Go %s, older than the %s expected" % (source, version, min_version),
            )
