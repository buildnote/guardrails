#!/usr/bin/env python3
from guardrail import Guardrail

CENTRAL = "Directory.Packages.props"

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    dotnet = guardrail.facts("dotnet", "no .NET project in %s" % project_dir)

    if dotnet.get("incomplete"):
        guardrail.skip(dotnet["incomplete"])

    if not dotnet["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    unreadable = dict((it["path"], it["reason"]) for it in dotnet["unparsed"])

    if not dotnet["centralPackageManagement"] and CENTRAL in unreadable:
        guardrail.skip("%s could not be read: %s" % (CENTRAL, unreadable[CENTRAL]))

    if not dotnet["centralPackageManagement"]:
        guardrail.violation(
            dotnet["manifest"] or project_dir,
            "The .NET build in %s leaves every project file to decide its own package versions, so two projects in "
            "the same solution can restore different versions of the same package" % project_dir,
        )
    else:
        guardrail.log("%s decides the package versions" % CENTRAL)
