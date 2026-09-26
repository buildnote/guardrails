#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    github = guardrail.facts("github", "no workflows were collected")
    longest = guardrail.number("maxMinutes", 60)

    if "workflows" not in github:
        guardrail.skip("the repository carries no GitHub Actions workflow")

    for workflow in github["workflows"]:
        for job in workflow["jobs"]:
            if job["uses"]:
                continue

            timeout = job["timeoutMinutes"]

            if timeout is None:
                guardrail.violation(
                    "%s %s" % (workflow["path"], job["id"]),
                    "Job %s in %s declares no timeout" % (job["id"], workflow["path"])
                )
            elif isinstance(timeout, int) and timeout > longest:
                guardrail.violation(
                    "%s %s" % (workflow["path"], job["id"]),
                    "Job %s in %s may run for %d minutes, over the %d it is allowed" % (
                        job["id"], workflow["path"], timeout, longest
                    )
                )
