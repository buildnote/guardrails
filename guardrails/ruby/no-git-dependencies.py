#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    ruby = guardrail.facts("ruby", "no Ruby project in %s" % project_dir)

    if ruby.get("incomplete"):
        guardrail.skip(ruby["incomplete"])

    if not ruby["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    from_git = [it for it in ruby["dependencies"]["direct"] if it["origin"] == "git"]

    for gem in from_git:
        guardrail.violation(
            "%s (%s)" % (gem["source"], gem["name"]),
            "%s declares %s from a git repository rather than from a gem source, so what an update installs is "
            "whatever that ref points at on the day it runs and no index ever published it"
            % (gem["source"], gem["name"]),
        )

    scanned = ruby["scanned"]

    if not from_git and scanned:
        guardrail.log(
            "no gem is fetched from git in %s, read by pattern rather than as a declaration, so a gem added inside "
            "a condition, a loop or an eval is not seen" % ", ".join(scanned)
        )
