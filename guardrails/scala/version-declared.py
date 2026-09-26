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
    min_version = guardrail.input("minVersion", "2.13")
    scala = guardrail.facts("scala", "no sbt build in %s" % project_dir)

    if scala.get("incomplete"):
        guardrail.skip(scala["incomplete"])

    if not scala["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if scala["unparsed"]:
        guardrail.skip(", ".join("%s: %s" % (it["path"], it["reason"]) for it in scala["unparsed"]))

    declared = scala["declared"]
    manifest = scala["manifest"] or project_dir

    if not declared:
        guardrail.violation(
            manifest,
            "No Scala version declared in %s, so the build compiles against whichever version the sbt launcher "
            "on the runner was itself built with" % manifest,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Scala %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Scala %s)" % (source, version),
                "%s asks for Scala %s, older than the %s expected" % (source, version, min_version),
            )
