#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    maven = guardrail.facts("maven", "no Maven build in %s" % project_dir)
    malformed = maven.get("malformed")

    if maven.get("incomplete") and not malformed:
        guardrail.skip(maven["incomplete"])

    if not maven["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if malformed:
        guardrail.violation(
            maven["pom"],
            "%s is not well formed XML, so Maven cannot build it and nothing else can read it either: the "
            "coordinates, the properties, the modules and the dependencies of this project are all unknown"
            % maven["pom"],
        )
    else:
        guardrail.log("%s parses" % maven["pom"])
