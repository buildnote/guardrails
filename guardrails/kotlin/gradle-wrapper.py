#!/usr/bin/env python3
import os

from guardrail import Guardrail

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    gradle = guardrail.facts("gradle", "no Gradle build in %s" % project_dir)

    if not gradle["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    wrapper = gradle["wrapper"]

    if not wrapper["script"]:
        guardrail.violation("gradlew", "Gradle wrapper file gradlew is not committed")

    if wrapper["properties"] is None:
        guardrail.violation(
            WRAPPER_PROPERTIES,
            "Gradle wrapper file %s is not committed" % WRAPPER_PROPERTIES,
        )
    elif wrapper["distributionUrl"] is None:
        guardrail.violation(
            WRAPPER_PROPERTIES,
            "%s declares no distributionUrl, so the Gradle version is not pinned" % WRAPPER_PROPERTIES,
        )
