#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    java = guardrail.facts("java", "no Gradle or Maven build in %s" % project_dir)

    if java.get("incomplete"):
        guardrail.skip(java["incomplete"])

    if not java["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    read = ", ".join(java["sources"]) or project_dir

    if not java["toolchain"]:
        guardrail.violation(
            read,
            "No Java toolchain is declared in %s, so the JDK the build compiles against is whichever one the runner "
            "happens to start it with rather than one the build provisions" % read,
        )
    else:
        declared = java["declared"] or {}

        if declared.get("mechanism") == "toolchain":
            guardrail.log("%s selects Java %s with a toolchain" % (declared["source"], declared["version"]))
        else:
            selecting = [it["path"] for it in java["projects"] if (it["declared"] or {}).get("mechanism") == "toolchain"]
            guardrail.log("a toolchain selects the JDK for the Gradle projects %s" % ", ".join(selecting))
