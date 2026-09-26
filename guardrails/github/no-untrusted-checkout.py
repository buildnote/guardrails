#!/usr/bin/env python3
from guardrail import Guardrail

CHECKOUT = "actions/checkout"

REF_KEYS = ("ref", "repository")

UNTRUSTED_MARKERS = (
    "github.event.pull_request.head",
    "github.event.pull_request.merge_commit_sha",
    "github.event.workflow_run.head",
    "refs/pull/",
)


def checks_out_a_chosen_ref(step):
    return step["action"] == CHECKOUT and any(key in REF_KEYS for key in step["withKeys"])


def runs_untrusted_reference(step):
    return any(any(marker in expression for marker in UNTRUSTED_MARKERS) for expression in step["interpolations"])


with Guardrail() as guardrail:
    github = guardrail.facts("github", "no workflows were collected")

    if "workflows" not in github:
        guardrail.skip("the repository carries no GitHub Actions workflow")

    untrusted = dict((entry["path"], entry["trigger"]) for entry in github["untrustedTriggers"])

    for workflow in github["workflows"]:
        trigger = untrusted.get(workflow["path"])

        if trigger is None:
            continue

        for job in workflow["jobs"]:
            for step in job["steps"]:
                if checks_out_a_chosen_ref(step):
                    guardrail.violation(
                        "%s %s" % (workflow["path"], job["id"]),
                        "%s runs on %s and checks out a ref of its own choosing, which under that trigger "
                        "runs untrusted code with this repository's secrets" % (workflow["path"], trigger)
                    )
                elif runs_untrusted_reference(step):
                    guardrail.violation(
                        "%s %s" % (workflow["path"], job["id"]),
                        "%s runs on %s and passes the request's own revision into a command, "
                        "which runs untrusted code with this repository's secrets" % (workflow["path"], trigger)
                    )
