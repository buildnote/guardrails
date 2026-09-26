#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail

with Guardrail() as guardrail:
    docker = guardrail.facts("docker", "no Docker facts were collected")
    final_only = guardrail.input("finalStageOnly", "true").strip().lower() != "false"
    ignored = [it.strip() for it in guardrail.input("ignore", "").split(",") if it.strip()]

    dockerfiles = docker.get("dockerfiles") or []

    if not dockerfiles:
        guardrail.skip("no Dockerfile was collected")

    for dockerfile in dockerfiles:
        where = dockerfile["path"]

        if any(fnmatch.fnmatch(where, pattern) for pattern in ignored):
            guardrail.log("%s is ignored by configuration" % where)
            continue

        if dockerfile["healthcheck"]:
            continue

        if final_only and len(dockerfile["stages"]) > 1:
            final = dockerfile["stages"][-1]["name"] or dockerfile["stages"][-1]["image"]
            guardrail.violation(
                where,
                "%s declares no HEALTHCHECK, so nothing tells the runtime whether the image its last stage (%s) builds is working or only running"
                % (where, final),
            )
        else:
            guardrail.violation(
                where,
                "%s declares no HEALTHCHECK, so nothing tells the runtime whether the container is working or only running"
                % where,
            )
