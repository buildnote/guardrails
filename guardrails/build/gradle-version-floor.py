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
    min_version = guardrail.input("minVersion", "8.0")
    gradle = guardrail.facts("gradle", "no Gradle build in %s" % project_dir)

    if not gradle["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    version = gradle["wrapper"]["version"]

    if version is None:
        guardrail.skip("the wrapper names no Gradle version to judge")

    guardrail.log("the wrapper pins Gradle %s" % version)

    if older(version, min_version):
        guardrail.violation(
            "Gradle %s" % version,
            "The wrapper pins Gradle %s, older than the %s expected" % (version, min_version),
        )
