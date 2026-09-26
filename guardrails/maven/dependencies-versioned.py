#!/usr/bin/env python3
from guardrail import Guardrail


def declared_in(dependency):
    profile = dependency.get("profile")
    source = dependency["source"]

    return "%s under profile %s" % (source, profile) if profile else source


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    maven = guardrail.facts("maven", "no Maven build in %s" % project_dir)

    if maven.get("incomplete"):
        guardrail.skip(maven["incomplete"])

    if not maven["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    direct = [it for it in maven["dependencies"]["direct"] if not it.get("platform")]
    unversioned = [it for it in direct if it["version"] is None]

    for dependency in unversioned:
        guardrail.violation(
            "%s (%s)" % (dependency["path"], declared_in(dependency)),
            "%s in %s takes no version from the entry itself, from dependencyManagement, from an imported BOM or from "
            "a property, so what this build compiles against is decided outside the checkout rather than by "
            "this commit" % (dependency["path"], declared_in(dependency)),
        )

    if not unversioned:
        guardrail.log("%d declared dependencies, every one resolving to a version" % len(direct))
