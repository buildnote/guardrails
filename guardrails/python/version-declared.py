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
    min_version = guardrail.input("minVersion", "3.9")
    python = guardrail.facts("python", "no Python project in %s" % project_dir)

    if python.get("incomplete"):
        guardrail.skip(python["incomplete"])

    if not python["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = python["declared"]
    read = ", ".join(python["sources"]) or project_dir

    if not declared:
        guardrail.violation(
            read,
            "No Python version declared in %s, so the interpreter a build runs on is whichever one the runner "
            "happens to carry" % read,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Python %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Python %s)" % (source, version),
                "%s asks for Python %s, older than the %s expected" % (source, version, min_version),
            )
