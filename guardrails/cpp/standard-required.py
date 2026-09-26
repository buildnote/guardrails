#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
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
        guardrail.skip("%s declares no C++ standard for the build to require" % project_dir)

    version, source = declared["version"], declared["source"]

    if not declared["pinned"]:
        guardrail.violation(
            source,
            "%s asks for C++%s without requiring it, so a compiler that does not offer that standard drops to an "
            "older one and the same commit compiles differently on a different machine" % (source, version),
        )
    else:
        guardrail.log("%s requires C++%s" % (source, version))
