#!/usr/bin/env python3
import re

from guardrail import Guardrail

MONIKER = re.compile(r"^net(\d+)\.(\d+)(?:-[0-9A-Za-z.]+)?$")


def release(moniker):
    found = MONIKER.match(moniker or "")

    return (int(found.group(1)), int(found.group(2))) if found else None


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_framework = guardrail.input("minFramework", "net8.0")
    dotnet = guardrail.facts("dotnet", "no .NET project in %s" % project_dir)

    if dotnet.get("incomplete"):
        guardrail.skip(dotnet["incomplete"])

    if not dotnet["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    frameworks = dotnet["targetFrameworks"]
    dropped = dotnet["dropped"]

    if not frameworks and dropped:
        guardrail.skip(
            "%d project files were left out because maxProjects was reached, so no target framework was read"
            % dropped
        )

    floor = release(min_framework)

    if floor is None:
        guardrail.skip("minFramework '%s' is not a net<major>.<minor> moniker" % min_framework)

    if dropped:
        guardrail.log("%d project files were left out of the facts by the collector" % dropped)

    for moniker in frameworks:
        targeted = release(moniker)

        if targeted is None or targeted >= floor:
            continue

        declaring = [it["manifest"] for it in dotnet["projects"] if moniker in it["targetFrameworks"]]
        named = ", ".join(declaring) or dotnet["manifest"] or project_dir

        guardrail.violation(
            named,
            "%s targets %s, older than the %s expected, so it builds on a framework that stops receiving security "
            "fixes sooner than the rest of the solution" % (named, moniker, min_framework),
        )
