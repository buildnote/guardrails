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
    min_version = guardrail.input("minVersion", "8.1")
    php = guardrail.facts("php", "no Composer project in %s" % project_dir)

    if php.get("incomplete"):
        guardrail.skip(php["incomplete"])

    if not php["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = php["declared"]
    read = ", ".join(php["sources"]) or project_dir

    if not declared:
        guardrail.violation(
            read,
            "No PHP version declared in %s, so Composer resolves against whichever runtime the machine running the "
            "install happens to carry" % read,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for PHP %s" % (source, version))

        if min_version and older(version, min_version):
            guardrail.violation(
                "%s (PHP %s)" % (source, version),
                "%s asks for PHP %s, older than the %s expected" % (source, version, min_version),
            )
