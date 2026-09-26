#!/usr/bin/env python3
import re

from guardrail import Guardrail


def numbers(version):
    return tuple(int(re.sub(r"\D.*", "", part) or 0) for part in version.split("."))


def older(version, floor):
    left, right = numbers(version), numbers(floor)
    size = max(len(left), len(right))
    return left + (0,) * (size - len(left)) < right + (0,) * (size - len(right))


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_version = guardrail.input("minVersion", "1.8")
    kotlin = guardrail.facts("kotlin", "no Gradle or Maven build in %s" % project_dir)

    if kotlin.get("incomplete"):
        guardrail.skip(kotlin["incomplete"])

    readable = kotlin["sources"]
    pinned = kotlin["declared"]

    if not readable:
        guardrail.skip("no Gradle or Maven build in %s" % project_dir)

    if not pinned:
        guardrail.violation(
            ", ".join(readable),
            "No Kotlin version declared in %s" % ", ".join(readable),
        )
    else:
        source, version = pinned["source"], pinned["version"]
        guardrail.log("%s pins Kotlin %s" % (source, version))
        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Kotlin %s)" % (source, version),
                "%s pins Kotlin %s, older than the %s expected" % (source, version, min_version),
            )
