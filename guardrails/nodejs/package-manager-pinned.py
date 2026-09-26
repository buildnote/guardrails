#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    nodejs = guardrail.facts("nodejs", "no Node.js project in %s" % project_dir)

    if nodejs.get("incomplete"):
        guardrail.skip(nodejs["incomplete"])

    if not nodejs["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    manifest = nodejs["manifest"] or project_dir
    manager = nodejs["packageManager"]
    version = manager.partition("@")[2] if manager else ""

    if not manager:
        guardrail.violation(
            manifest,
            "%s names no packageManager, so Corepack installs nothing and the install runs under whichever npm, "
            "pnpm or yarn the runner happens to carry" % manifest,
        )
    elif not version or not version[0].isdigit():
        guardrail.violation(
            "%s (packageManager %s)" % (manifest, manager),
            "%s names the package manager as '%s', which is not one exact version, so Corepack has nothing to "
            "install and the version the install runs under is whichever the runner happens to carry"
            % (manifest, manager),
        )
    else:
        guardrail.log("Corepack installs %s" % manager)
