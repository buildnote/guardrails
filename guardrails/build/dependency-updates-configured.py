#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_PATHS = (
    ".github/dependabot.yml,.github/dependabot.yaml,renovate.json,renovate.json5,"
    ".renovaterc,.renovaterc.json,.github/renovate.json"
)

with Guardrail() as guardrail:
    paths = [it.strip() for it in guardrail.input("paths", DEFAULT_PATHS).split(",") if it.strip()]
    files = guardrail.facts("files")["files"]

    described = [(path, files[path]) for path in paths if path in files]

    if not described:
        guardrail.skip("none of %s was collected" % ", ".join(paths))

    configured = [path for path, it in described if it["present"]]

    if configured:
        guardrail.log("dependency updates are configured by %s" % ", ".join(configured))
    else:
        guardrail.violation(
            paths[0],
            "The repository automates no dependency update: none of %s is there, so an upgrade only happens "
            "when somebody makes time for it" % ", ".join(paths),
        )
