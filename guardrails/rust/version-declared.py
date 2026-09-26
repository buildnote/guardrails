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
    min_version = guardrail.input("minVersion", "1.70")
    rust = guardrail.facts("rust", "no Cargo build in %s" % project_dir)

    if rust.get("incomplete"):
        guardrail.skip(rust["incomplete"])

    if not rust["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = rust["declared"]
    manifest = rust["manifest"] or project_dir

    if not declared:
        guardrail.violation(
            manifest,
            "No Rust version declared in %s, so the compiler a build runs on is whichever one the runner happens "
            "to carry" % manifest,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Rust %s" % (source, version))

        if not declared["pinned"]:
            guardrail.violation(
                "%s (Rust %s)" % (source, version),
                "%s asks for the %s channel, which moves under the build, so a rerun of this commit compiles on "
                "whichever release that channel points at on the day" % (source, version),
            )
        elif min_version and older(version, min_version):
            guardrail.violation(
                "%s (Rust %s)" % (source, version),
                "%s asks for Rust %s, older than the %s expected" % (source, version, min_version),
            )
