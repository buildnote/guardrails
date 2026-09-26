#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail


def exempt(name, patterns):
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


with Guardrail() as guardrail:
    jenkins = guardrail.facts("jenkins", "no Jenkinsfiles were collected")
    allowed = [it.strip() for it in guardrail.input("allow", "").split(",") if it.strip()]

    if jenkins.get("source") == "none":
        guardrail.skip(jenkins.get("reason", "no Jenkinsfile was found"))

    readable = [
        pipeline for pipeline in jenkins["pipelines"]
        if pipeline["style"] == "declarative" or pipeline["libraries"]
    ]

    if not readable:
        guardrail.skip(
            "every Jenkinsfile that was read is a scripted pipeline declaring no library that could be read"
        )

    for pipeline in jenkins["pipelines"]:
        if pipeline["style"] != "declarative":
            guardrail.log(
                "%s is a scripted pipeline, so the libraries read from it are a floor rather than all of them"
                % pipeline["path"]
            )

        for library in pipeline["libraries"]:
            if library["pinned"] or exempt(library["name"], allowed):
                continue

            if library["ref"] is None:
                message = "%s loads the shared library %s with no version, so it takes whatever the controller defaults to" % (
                    pipeline["path"], library["name"]
                )
            else:
                message = "%s loads the shared library %s from %s, which does not name a fixed revision" % (
                    pipeline["path"], library["name"], library["ref"]
                )

            guardrail.violation("%s %s" % (pipeline["path"], library["name"]), message)
