#!/usr/bin/env python3
import fnmatch

from guardrail import Guardrail

DEFAULT_PATTERNS = "*SECRET*,*TOKEN*,*PASSWORD*,*KEY*,*CREDENTIAL*"

DECLARED = (
    ("ARG", "buildArgs", "the build argument", "is recorded in the image history"),
    ("ENV", "envKeys", "the environment variable", "stays in the image"),
)


def matching(name, patterns):
    for pattern in patterns:
        if fnmatch.fnmatchcase(name.upper(), pattern):
            return pattern

    return None


with Guardrail() as guardrail:
    docker = guardrail.facts("docker", "no Dockerfile facts were collected")
    patterns = [it.strip().upper() for it in guardrail.input("patterns", DEFAULT_PATTERNS).split(",") if it.strip()]
    dockerfiles = docker.get("dockerfiles") or []

    if not dockerfiles:
        guardrail.skip(docker.get("reason") or "no Dockerfile was collected")

    if not patterns:
        guardrail.skip("no patterns are configured, so no name can be judged")

    for dockerfile in dockerfiles:
        path = dockerfile["path"]

        for keyword, fact, described, kept in DECLARED:
            for name in dockerfile[fact]:
                pattern = matching(name, patterns)

                if pattern is None:
                    continue

                guardrail.violation(
                    "%s %s %s" % (path, keyword, name),
                    "The Dockerfile %s declares %s %s, whose name matches %s, and an %s %s, so its value reaches everyone who can pull the image."
                    % (path, described, name, pattern, keyword, kept)
                )
