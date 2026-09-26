#!/usr/bin/env python3
from guardrail import Guardrail

SNAPSHOT = "-SNAPSHOT"


def declared_in(dependency):
    profile = dependency.get("profile")
    source = dependency["source"]

    return "%s under profile %s" % (source, profile) if profile else source


def kind(dependency):
    return "The BOM" if dependency.get("platform") else "The dependency"


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    maven = guardrail.facts("maven", "no Maven build in %s" % project_dir)

    if maven.get("incomplete"):
        guardrail.skip(maven["incomplete"])

    if not maven["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    direct = maven["dependencies"]["direct"]
    snapshots = [it for it in direct if (it["version"] or "").endswith(SNAPSHOT)]

    for dependency in snapshots:
        guardrail.violation(
            "%s %s (%s)" % (dependency["path"], dependency["version"], declared_in(dependency)),
            "%s %s is at %s in %s, and a snapshot is republished under the same coordinates, so the artifact this "
            "commit shipped cannot be built again from it"
            % (kind(dependency), dependency["path"], dependency["version"], declared_in(dependency)),
        )

    if not snapshots:
        guardrail.log("read %d declared dependencies, none at a snapshot version" % len(direct))
