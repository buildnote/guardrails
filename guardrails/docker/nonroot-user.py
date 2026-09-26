#!/usr/bin/env python3
from guardrail import Guardrail

ROOT = ("root", "0")

with Guardrail() as guardrail:
    docker = guardrail.facts("docker", "no Dockerfile facts were collected")
    dockerfiles = docker.get("dockerfiles") or []

    if not dockerfiles:
        guardrail.skip(docker.get("reason") or "no Dockerfile was collected")

    for dockerfile in dockerfiles:
        path = dockerfile["path"]
        user = dockerfile["user"]

        if user is None:
            guardrail.violation(
                path,
                "The Dockerfile %s declares no USER, so everything the image runs, runs as root." % path
            )
            continue

        if "$" in user:
            guardrail.log("%s ends as USER %s, which the collected names cannot resolve" % (path, user))
            continue

        if user.split(":")[0].strip().lower() in ROOT:
            guardrail.violation(
                "%s USER %s" % (path, user),
                "The Dockerfile %s ends on USER %s, so the container runs its process as uid 0." % (path, user)
            )
