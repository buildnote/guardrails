#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_EXPRESSIONS = (
    "github.event.issue.title,github.event.issue.body,"
    "github.event.pull_request.title,github.event.pull_request.body,"
    "github.event.pull_request.head.ref,github.event.pull_request.head.label,"
    "github.event.pull_request.head.repo,github.event.comment.body,"
    "github.event.review.body,github.event.review_comment.body,"
    "github.event.discussion.title,github.event.discussion.body,"
    "github.event.commits,github.event.head_commit.message,github.event.head_commit.author,"
    "github.event.pages,github.event.workflow_run.head_branch,"
    "github.event.workflow_run.head_commit.message,github.head_ref"
)


def untrusted_in(expression, prefixes):
    normalised = "".join(expression.split())

    return [prefix for prefix in prefixes if prefix in normalised]


with Guardrail() as guardrail:
    github = guardrail.facts("github", "no workflows were collected")
    prefixes = [it.strip() for it in guardrail.input("expressions", DEFAULT_EXPRESSIONS).split(",") if it.strip()]

    if "workflows" not in github:
        guardrail.skip("the repository carries no GitHub Actions workflow")

    for workflow in github["workflows"]:
        for job in workflow["jobs"]:
            for step in job["steps"]:
                if step["run"] is None:
                    continue

                for expression in step["interpolations"]:
                    named = untrusted_in(expression, prefixes)

                    if not named:
                        continue

                    guardrail.violation(
                        "%s %s: %s" % (workflow["path"], job["id"], expression),
                        "%s interpolates %s into the shell body of a step in %s, so text an outsider writes is "
                        "substituted into the script before it runs"
                        % (workflow["path"], named[0], job["id"]),
                    )
