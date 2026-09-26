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
    min_version = guardrail.input("minVersion", "1.11")
    clojure = guardrail.facts("clojure", "no Clojure build in %s" % project_dir)

    if clojure.get("incomplete"):
        guardrail.skip(clojure["incomplete"])

    if not clojure["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if not clojure["sources"]:
        guardrail.skip("no manifest in %s could be read as a Clojure build" % project_dir)

    declared = clojure["declared"]
    read = ", ".join(clojure["sources"])
    scanned = ", ".join(clojure["scanned"])

    if not declared and scanned:
        guardrail.skip(
            "%s is Clojure read by pattern, so a version it depends on inside a function or a reader conditional "
            "is not among what was read" % scanned
        )

    if not declared:
        guardrail.violation(
            read,
            "No Clojure version declared in %s, so the release a build compiles against is whichever one the "
            "installed tool falls back to" % read,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for Clojure %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (Clojure %s)" % (source, version),
                "%s asks for Clojure %s, older than the %s expected" % (source, version, min_version),
            )
