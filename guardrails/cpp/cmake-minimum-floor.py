#!/usr/bin/env python3
import re

from guardrail import Guardrail

NUMBERS = re.compile(r"\d+(?:\.\d+)*")


def policy(version):
    found = NUMBERS.findall(version or "")

    return found[-1] if found else None


def numbers(version):
    resolved = policy(version)

    return tuple(int(part) for part in resolved.split(".")) if resolved else None


def older(version, floor):
    left, right = numbers(version), numbers(floor)

    if left is None or right is None:
        return False

    size = max(len(left), len(right))

    return left + (0,) * (size - len(left)) < right + (0,) * (size - len(right))


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_version = guardrail.input("minVersion", "3.20")
    cpp = guardrail.facts("cpp", "no C or C++ build in %s" % project_dir)

    if cpp.get("incomplete"):
        guardrail.skip(cpp["incomplete"])

    if not cpp["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if cpp["buildSystem"] != "cmake":
        guardrail.skip("%s is not a CMake build" % project_dir)

    manifest = cpp["manifest"]
    required = policy(cpp["cmakeMinimum"])

    if not required:
        guardrail.violation(
            manifest,
            "%s names no cmake_minimum_required, so the build configures under whichever policy defaults the "
            "installed CMake carries" % manifest,
        )
    elif older(required, min_version):
        guardrail.violation(
            "%s (CMake %s)" % (manifest, required),
            "%s configures under CMake %s policies, older than the %s expected, so the build keeps the behaviour "
            "older CMake defaulted to for target properties, find_package search order and RPATH handling"
            % (manifest, required, min_version),
        )
    else:
        guardrail.log("%s configures under CMake %s policies" % (manifest, required))
