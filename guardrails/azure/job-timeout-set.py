#!/usr/bin/env python3
from guardrail import Guardrail


def named(job):
    return job["id"] or job["displayName"] or "the only job"


with Guardrail() as guardrail:
    azure = guardrail.facts("azure", "no Azure Pipelines definitions were collected")
    longest = guardrail.number("maxMinutes", 60)

    if azure.get("source") == "none":
        guardrail.skip(azure.get("reason", "no Azure Pipelines definition was found"))

    for pipeline in azure["pipelines"]:
        for job in pipeline["jobs"]:
            if job["template"]:
                continue

            timeout = job["timeoutInMinutes"]

            if timeout is None:
                guardrail.violation(
                    "%s %s" % (pipeline["path"], named(job)),
                    "Job %s in %s declares no timeout" % (named(job), pipeline["path"])
                )
            elif timeout == 0:
                guardrail.violation(
                    "%s %s" % (pipeline["path"], named(job)),
                    "Job %s in %s asks for the maximum timeout, which on a self hosted agent is no limit at all"
                    % (named(job), pipeline["path"])
                )
            elif isinstance(timeout, int) and timeout > longest:
                guardrail.violation(
                    "%s %s" % (pipeline["path"], named(job)),
                    "Job %s in %s may run for %d minutes, over the %d it is allowed" % (
                        named(job), pipeline["path"], timeout, longest
                    )
                )
