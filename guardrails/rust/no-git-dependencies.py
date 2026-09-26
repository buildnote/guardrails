#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    rust = guardrail.facts("rust", "no Cargo build in %s" % project_dir)

    if rust.get("incomplete"):
        guardrail.skip(rust["incomplete"])

    if not rust["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    direct = rust["dependencies"]["direct"]
    fetched = [it for it in direct if it["origin"] == "git"]
    dropped = rust["dropped"]

    if not fetched and dropped:
        guardrail.skip(
            "%d workspace members were left out of the facts, so the dependencies collected are part of the build "
            "rather than all of it" % dropped
        )

    for dependency in fetched:
        guardrail.violation(
            "%s in %s" % (dependency["name"], dependency["source"]),
            "%s declares %s as a git dependency, which resolves from a URL nobody versions or audits, so what a "
            "build of this commit compiles against is whatever that repository serves"
            % (dependency["source"], dependency["name"]),
        )

    if not fetched:
        guardrail.log("%d direct dependencies, none fetched from a git URL" % len(direct))
