#!/usr/bin/env python3
from guardrail import Guardrail

NAMED = ("groupId", "artifactId", "version")


def listed(names):
    if len(names) == 1:
        return names[0]

    return "%s and %s" % (", ".join(names[:-1]), names[-1])


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    maven = guardrail.facts("maven", "no Maven build in %s" % project_dir)

    if maven.get("incomplete"):
        guardrail.skip(maven["incomplete"])

    if not maven["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    coordinates = maven["coordinates"]
    missing = [name for name in NAMED if not coordinates[name]]

    if missing:
        guardrail.violation(
            maven["pom"],
            "%s declares no %s and inherits none from a parent, so the artifact this build publishes cannot be "
            "named by whoever depends on it or traced back to this commit" % (maven["pom"], listed(missing)),
        )
    else:
        guardrail.log(
            "publishes %s:%s:%s"
            % (coordinates["groupId"], coordinates["artifactId"], coordinates["version"])
        )
