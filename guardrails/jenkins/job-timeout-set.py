#!/usr/bin/env python3
from guardrail import Guardrail


def named(stage):
    return stage["name"] or "an unnamed stage"


with Guardrail() as guardrail:
    jenkins = guardrail.facts("jenkins", "no Jenkinsfiles were collected")
    longest = guardrail.number("maxMinutes", 60)

    if jenkins.get("source") == "none":
        guardrail.skip(jenkins.get("reason", "no Jenkinsfile was found"))

    declarative = [pipeline for pipeline in jenkins["pipelines"] if pipeline["style"] == "declarative"]

    if not declarative:
        guardrail.skip("every Jenkinsfile that was read is a scripted pipeline, whose timeouts are not readable")

    for pipeline in declarative:
        path = pipeline["path"]

        if pipeline["timeout"] is not None:
            minutes = pipeline["timeoutMinutes"]

            if minutes is not None and minutes > longest:
                guardrail.violation(
                    path,
                    "%s may run for %d minutes, over the %d it is allowed" % (path, minutes, longest)
                )

            continue

        if not pipeline["stages"]:
            guardrail.violation(path, "%s declares no timeout" % path)
            continue

        guarded = {}

        for position, stage in enumerate(pipeline["stages"]):
            inherited = guarded.get(stage["parent"], False)
            declared = stage["timeout"] is not None
            minutes = stage["timeoutMinutes"]

            guarded[position] = declared or inherited

            if declared and minutes is not None and minutes > longest:
                guardrail.violation(
                    "%s %s" % (path, named(stage)),
                    "Stage %s in %s may run for %d minutes, over the %d it is allowed" % (
                        named(stage), path, minutes, longest
                    )
                )
            elif not declared and not inherited:
                guardrail.violation(
                    "%s %s" % (path, named(stage)),
                    "Stage %s in %s declares no timeout, and neither does the pipeline holding it" % (
                        named(stage), path
                    )
                )
