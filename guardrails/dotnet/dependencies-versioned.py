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

    direct = dotnet["dependencies"]["direct"]
    dropped = dotnet["dropped"]

    if not direct and dropped:
        guardrail.skip(
            "%d project files were left out because maxProjects was reached, so no package reference was read"
            % dropped
        )

    unversioned = [it for it in direct if it["version"] is None and it["managedBy"] is None]
    unreadable = dict((it["path"], it["reason"]) for it in dotnet["unparsed"])

    if unversioned and CENTRAL in unreadable:
        guardrail.skip(
            "%s could not be read (%s), so whether it supplies these versions centrally is unknown"
            % (CENTRAL, unreadable[CENTRAL])
        )

    if dropped:
        guardrail.log("%d project files were left out of the facts by the collector" % dropped)

    for reference in unversioned:
        guardrail.violation(
            "%s (%s)" % (reference["source"], reference["name"]),
            "%s references %s with no version of its own and no central PackageVersion, so a restore takes "
            "whichever version NuGet picks" % (reference["source"], reference["name"]),
        )

    if not unversioned:
        guardrail.log("%d package references are versioned" % len(direct))
