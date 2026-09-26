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


def declarations(java):
    found = {}

    for project in java["projects"]:
        if project["declared"]:
            found[project["declared"]["source"]] = project["declared"]

    if java["declared"]:
        found.setdefault(java["declared"]["source"], java["declared"])

    return found


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_version = guardrail.input("minVersion", "17")
    java = guardrail.facts("java", "no Gradle or Maven build in %s" % project_dir)

    if java.get("incomplete"):
        guardrail.skip(java["incomplete"])

    if not java["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = declarations(java)
    read = ", ".join(java["sources"]) or project_dir

    if not declared:
        guardrail.violation(
            read,
            "No Java version declared in %s, and none in any project it includes, so the release the build "
            "compiles for is whichever one the JDK running it defaults to" % read,
        )

    for source, declaration in declared.items():
        version = declaration["version"]
        guardrail.log("%s asks for Java %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Java %s)" % (source, version),
                "%s asks for Java %s, older than the %s expected" % (source, version, min_version),
            )
