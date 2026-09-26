#!/usr/bin/env python3
import re

from guardrail import Guardrail

NUMBER = re.compile(r"\d+")


def year(standard):
    found = NUMBER.search(str(standard))

    if not found:
        return None

    number = int(found.group(0))

    return 1900 + number if number >= 90 else 2000 + number


def older(standard, floor):
    left, right = year(standard), year(floor)

    return left is not None and right is not None and left < right


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_standard = guardrail.number("minStandard", 17)
    cpp = guardrail.facts("cpp", "no C or C++ build in %s" % project_dir)

    if cpp.get("incomplete"):
        guardrail.skip(cpp["incomplete"])

    if not cpp["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if cpp["buildSystem"] != "cmake":
        guardrail.skip("%s is not a CMake build, and the standard is only read from CMakeLists.txt" % project_dir)

    languages = cpp["languages"]

    if languages and "CXX" not in languages:
        guardrail.skip(
            "%s enables %s rather than C++, so it has no C++ standard to declare"
            % (project_dir, ", ".join(languages))
        )

    declared = cpp["declared"]

    if not declared:
        guardrail.violation(
            cpp["manifest"] or project_dir,
            "The CMake build in %s declares no C++ standard, so what it compiles against is whichever standard "
            "the compiler on the runner defaults to" % project_dir,
        )
    else:
        version, source = declared["version"], declared["source"]
        guardrail.log("%s asks for C++%s" % (source, version))

        if older(version, min_standard):
            guardrail.violation(
                "%s (C++%s)" % (source, version),
                "%s asks for C++%s, older than the C++%s expected" % (source, version, min_standard),
            )
