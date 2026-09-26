#!/usr/bin/env python3
from guardrail import Guardrail

DOCKER_HUB = "docker.io"


def labelled(stage, index):
    return 'stage "%s"' % stage["name"] if stage["name"] else "stage %d" % index


def evidence(path, stage, index, found=""):
    return "%s stage %s%s" % (path, stage["name"] or index, found)


def unresolved(stage):
    return "$" in (stage["image"] or "")


def unpinned(stage, allow_tags):
    if stage["digest"]:
        return None
    if not allow_tags:
        return "pins no digest"
    if not stage["tag"]:
        return "names no tag, so it resolves to latest"
    if stage["tag"].lower() == "latest":
        return "is pinned to latest"

    return None


with Guardrail() as guardrail:
    docker = guardrail.facts("docker", "no Dockerfile facts were collected")
    allow_tags = guardrail.input("allowTags", "false").strip().lower() == "true"
    registries = [it.strip().lower() for it in guardrail.input("registries", "").split(",") if it.strip()]
    dockerfiles = docker.get("dockerfiles") or []

    if not dockerfiles:
        guardrail.skip(docker.get("reason") or "no Dockerfile was collected")

    for dockerfile in dockerfiles:
        path = dockerfile["path"]
        built = []

        for index, stage in enumerate(dockerfile["stages"], start=1):
            image = stage["image"]
            named = (stage["repository"] or image or "").lower()
            reuses = named in built or named == "scratch"

            if stage["name"]:
                built.append(stage["name"].lower())

            if reuses:
                continue

            if unresolved(stage):
                guardrail.log(
                    "%s builds %s from %s, which the collected names cannot resolve"
                    % (path, labelled(stage, index), image)
                )
                continue

            registry = (stage["registry"] or DOCKER_HUB).lower()

            if registries and registry not in registries:
                guardrail.violation(
                    evidence(path, stage, index, " registry"),
                    "The Dockerfile %s builds %s from %s, whose registry %s is not one of %s."
                    % (path, labelled(stage, index), image, registry, ", ".join(registries))
                )

            reason = unpinned(stage, allow_tags)

            if reason:
                guardrail.violation(
                    evidence(path, stage, index),
                    "The Dockerfile %s builds %s from %s, which %s, so a rebuild of this commit can start from a different image."
                    % (path, labelled(stage, index), image, reason)
                )
