#!/usr/bin/env python3
from guardrail import Guardrail


def constraint(dependency):
    return (dependency.get("version") or "").strip()


def unconstrained(dependency):
    written = constraint(dependency)

    return not written or written == "*"


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    php = guardrail.facts("php", "no Composer project in %s" % project_dir)

    if php.get("incomplete"):
        guardrail.skip(php["incomplete"])

    if not php["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    direct = php["dependencies"]["direct"]
    loose = [it for it in direct if unconstrained(it)]

    for dependency in loose:
        guardrail.violation(
            "%s (%s)" % (dependency["name"], dependency["source"]),
            "%s asks for %s in %s, so an install resolves to whatever the registry serves, including a major "
            "release this code has never been built against"
            % (dependency["name"], constraint(dependency) or "nothing at all", dependency["source"]),
        )

    if not loose:
        guardrail.log("%d direct requirements, every one constrained" % len(direct))
