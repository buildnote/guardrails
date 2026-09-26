#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail


def exempt(action, patterns):
    return any(fnmatch.fnmatch(action, pattern) for pattern in patterns)


with Guardrail() as guardrail:
    github = guardrail.facts("github", "no workflows were collected")
    allowed = [it.strip() for it in guardrail.input("allow", "").split(",") if it.strip()]

    if "workflows" not in github:
        guardrail.skip("the repository carries no GitHub Actions workflow")

    for workflow in github["workflows"]:
        for job in workflow["jobs"]:
            for step in job["steps"]:
                if step["uses"] is None or step["local"] or step["docker"]:
                    continue

                if step["pinned"]:
                    continue

                action = step["action"] or step["uses"]

                if exempt(action, allowed):
                    continue

                guardrail.violation(
                    "%s %s" % (workflow["path"], step["uses"]),
                    "%s runs %s, which is pinned to %s rather than to a commit sha" % (
                        workflow["path"], action, step["ref"] or "nothing"
                    )
                )
