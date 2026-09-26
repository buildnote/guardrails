#!/usr/bin/env python3
from guardrail import Guardrail


def message(dependency):
    if dependency["version"]:
        return (
            "%s in %s is declared at %s, which resolves to whatever the repository serves that day, so two builds "
            "of this commit can compile against different code"
            % (dependency["name"], dependency["source"], dependency["version"])
        )

    return (
        "%s in %s takes its revision from a reference rather than a literal, so the version it compiles against "
        "cannot be read out of the build" % (dependency["name"], dependency["source"])
    )


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
    unpinned = [it for it in direct if not it["pinned"]]

    for dependency in unpinned:
        guardrail.violation("%s (%s)" % (dependency["name"], dependency["source"]), message(dependency))

    if not unpinned:
        guardrail.log("read %d library dependencies, none at a moving or unresolved revision" % len(direct))

        if scala["scanned"]:
            guardrail.log(
                "%s: Scala read by pattern rather than a declaration, so that count is a floor rather than "
                "everything the build declares" % ", ".join(scala["scanned"])
            )
