#!/usr/bin/env python3
from guardrail import Guardrail

PROPERTIES = "project/build.properties"

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    scala = guardrail.facts("scala", "no sbt build in %s" % project_dir)

    if scala.get("incomplete"):
        guardrail.skip(scala["incomplete"])

    if not scala["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    sbt = scala["sbt"]

    if not sbt:
        guardrail.violation(
            PROPERTIES,
            "The sbt build in %s pins no launcher version in %s, so whichever sbt the runner carries decides how "
            "the build is resolved and run" % (project_dir, PROPERTIES),
        )
    else:
        guardrail.log("%s pins sbt %s" % (PROPERTIES, sbt))
