#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    gitlab = guardrail.facts("gitlab", "no GitLab CI files were collected")
    longest = guardrail.number("maxMinutes", 60)

    if "pipelines" not in gitlab:
        guardrail.skip("the repository carries no GitLab CI file")

    for pipeline in gitlab["pipelines"]:
        for job in pipeline["jobs"]:
            if job["trigger"]:
                continue

            declared = job["timeout"]
            minutes = job["timeoutMinutes"]

            if declared is None:
                guardrail.violation(
                    "%s %s" % (pipeline["path"], job["id"]),
                    "Job %s in %s declares no timeout, so it takes the project's own limit"
                    % (job["id"], pipeline["path"])
                )
            elif minutes is not None and minutes > longest:
                guardrail.violation(
                    "%s %s" % (pipeline["path"], job["id"]),
                    "Job %s in %s may run for %s, over the %d minutes it is allowed" % (
                        job["id"], pipeline["path"], declared, longest
                    )
                )
