#!/usr/bin/env python3
from guardrail import Guardrail

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    gradle = guardrail.facts("gradle", "no Gradle build in %s" % project_dir)

    if not gradle.get("exists"):
        guardrail.skip("%s is not a directory" % project_dir)

    wrapper = gradle["wrapper"]

    if wrapper["properties"] is None:
        guardrail.skip("%s does not commit the Gradle wrapper" % project_dir)

    if wrapper["distributionUrl"] is None:
        guardrail.skip("%s pins no distribution to verify" % wrapper["properties"])

    if wrapper.get("distributionSha256Sum") is None:
        guardrail.violation(
            wrapper["properties"],
            "%s pins no distributionSha256Sum, so the wrapper runs whatever %s serves it" % (
                wrapper["properties"], wrapper["distributionUrl"]
            )
        )
