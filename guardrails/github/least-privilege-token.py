#!/usr/bin/env python3
from guardrail import Guardrail

WRITE_ALL = "write-all"


def declared(value):
    return value is not None


with Guardrail() as guardrail:
    github = guardrail.facts("github", "no workflows were collected")
    allow_write_all = guardrail.input("allowWriteAll", "false").strip().lower() == "true"

    if "workflows" not in github:
        guardrail.skip("the repository carries no GitHub Actions workflow")

    for workflow in github["workflows"]:
        inherited = declared(workflow["permissions"])

        for job in workflow["jobs"]:
            if not inherited and not declared(job["permissions"]):
                guardrail.violation(
                    "%s %s" % (workflow["path"], job["id"]),
                    "Job %s in %s declares no permissions, and neither does the workflow, "
                    "so it takes whatever the repository grants by default" % (job["id"], workflow["path"])
                )

            if not allow_write_all and job["permissions"] == WRITE_ALL:
                guardrail.violation(
                    "%s %s" % (workflow["path"], job["id"]),
                    "Job %s in %s takes write access to everything" % (job["id"], workflow["path"])
                )

        if not allow_write_all and workflow["permissions"] == WRITE_ALL:
            guardrail.violation(
                "%s permissions" % workflow["path"],
                "%s takes write access to everything, so every job in it does" % workflow["path"]
            )
