#!/usr/bin/env python3

from guardrail import Guardrail


def declarations(java):
    found = {}

    for project in java["projects"]:
        if project["declared"]:
            found[project["declared"]["source"]] = project["declared"]

    if java["declared"]:
        found.setdefault(java["declared"]["source"], java["declared"])

    return found


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    java = guardrail.facts("java", "no Gradle or Maven build in %s" % project_dir)

    if java.get("incomplete"):
        guardrail.skip(java["incomplete"])

    if not java["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    declared = declarations(java)
    read = ", ".join(java["sources"]) or project_dir

    if not declared:
        guardrail.skip("nothing in %s declares a Java version" % read)

    for source, declaration in declared.items():
        version, mechanism = declaration["version"], declaration["mechanism"]

        if declaration["reproducible"]:
            guardrail.log("%s provisions Java %s by %s" % (source, version, mechanism))
        else:
            guardrail.violation(
                "%s (%s)" % (source, mechanism),
                "%s declares Java %s by %s rather than by a toolchain, so the build only targets that release and "
                "still compiles against the class library of whichever JDK the runner started"
                % (source, version, mechanism),
            )
