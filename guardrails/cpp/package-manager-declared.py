#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    cpp = guardrail.facts("cpp", "no C or C++ build in %s" % project_dir)

    if cpp.get("incomplete"):
        guardrail.skip(cpp["incomplete"])

    if not cpp["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    manager = cpp["packageManager"]

    if not manager:
        guardrail.violation(
            cpp["manifest"] or project_dir,
            "The C or C++ build in %s declares no package manager, so the versions it links against are whichever "
            "ones the machine building it already carries" % project_dir,
        )
    else:
        guardrail.log("dependencies come from %s" % manager)
