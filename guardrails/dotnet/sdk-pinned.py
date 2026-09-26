#!/usr/bin/env python3
import os

from guardrail import Guardrail

GLOBAL_JSON = "global.json"


def named(paths, name):
    return next((it for it in paths if os.path.basename(it) == name), None)

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    dotnet = guardrail.facts("dotnet", "no .NET project in %s" % project_dir)

    if dotnet.get("incomplete"):
        guardrail.skip(dotnet["incomplete"])

    if not dotnet["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = dotnet["declared"]
    unreadable = dict((os.path.basename(it["path"]), (it["path"], it["reason"])) for it in dotnet["unparsed"])

    if not declared and GLOBAL_JSON in unreadable:
        guardrail.skip("%s could not be read: %s" % unreadable[GLOBAL_JSON])

    if not declared:
        guardrail.violation(
            named(dotnet["sources"], GLOBAL_JSON) or dotnet["manifest"] or project_dir,
            "The .NET build in %s pins no SDK version, so it builds with whichever SDK the runner happens to "
            "carry" % project_dir,
        )
    elif not declared["pinned"]:
        guardrail.violation(
            "%s (SDK %s)" % (declared["source"], declared["version"]),
            "%s asks for SDK %s but rolls forward with %s, so a newer SDK installed on the runner takes the build "
            "instead" % (declared["source"], declared["version"], dotnet["rollForward"]),
        )
    else:
        guardrail.log("%s pins SDK %s" % (declared["source"], declared["version"]))
