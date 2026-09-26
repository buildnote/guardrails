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
    min_version = guardrail.input("minVersion", "3.0")
    ruby = guardrail.facts("ruby", "no Ruby project in %s" % project_dir)

    if ruby.get("incomplete"):
        guardrail.skip(ruby["incomplete"])

    if not ruby["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = ruby["declared"]
    read = ", ".join(ruby["sources"]) or project_dir

    if not declared:
        guardrail.violation(
            read,
            "No Ruby version declared in %s, so the interpreter a build and a deploy run on is whichever one the "
            "image happens to carry" % read,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Ruby %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Ruby %s)" % (source, version),
                "%s asks for Ruby %s, older than the %s expected" % (source, version, min_version),
            )
