#!/usr/bin/env python3
from guardrail import Guardrail

SNAPSHOT = "-SNAPSHOT"

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    scala = guardrail.facts("scala", "no sbt build in %s" % project_dir)

    if scala.get("incomplete"):
        guardrail.skip(scala["incomplete"])

    if not scala["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if scala["unparsed"]:
        guardrail.skip(", ".join("%s: %s" % (it["path"], it["reason"]) for it in scala["unparsed"]))

    direct = scala["dependencies"]["direct"]
    snapshots = [it for it in direct if (it["version"] or "").endswith(SNAPSHOT)]

    for dependency in snapshots:
        guardrail.violation(
            "%s %s (%s)" % (dependency["name"], dependency["version"], dependency["source"]),
            "%s is at %s in %s, and a snapshot is republished under the same coordinates, so the artifact this "
            "commit shipped cannot be built again from it"
            % (dependency["name"], dependency["version"], dependency["source"]),
        )

    if not snapshots:
        guardrail.log("read %d library dependencies, none at a snapshot revision" % len(direct))

        if scala["scanned"]:
            guardrail.log(
                "%s: Scala read by pattern rather than a declaration, so that count is a floor rather than "
                "everything the build declares" % ", ".join(scala["scanned"])
            )
