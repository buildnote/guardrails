#!/usr/bin/env python3
from guardrail import Guardrail

MANIFESTS = ["build.gradle.kts", "build.gradle", "pom.xml"]

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    gradle = guardrail.optional("gradle", {})
    maven = guardrail.optional("maven", {})

    if gradle.get("exists") is False or maven.get("exists") is False:
        guardrail.skip("%s is not a directory" % project_dir)

    found = [name for name in [gradle.get("manifest"), maven.get("pom")] if name]

    if not found:
        guardrail.violation(
            project_dir,
            "No build manifest in %s, expected one of %s" % (project_dir, ", ".join(MANIFESTS)),
        )
    else:
        guardrail.log("found %s" % ", ".join(found))
