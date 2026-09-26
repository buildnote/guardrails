#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    paths = [it.strip() for it in guardrail.input("paths", "LICENSE,LICENSE.md,LICENSE.txt,COPYING").split(",") if it.strip()]
    files = guardrail.facts("files")["files"]

    described = [files[path] for path in paths if path in files]

    if not described:
        guardrail.skip("none of %s was collected" % ", ".join(paths))

    if not any(it["present"] for it in described):
        guardrail.violation(
            paths[0],
            "The repository states no licence: none of %s is there" % ", ".join(paths),
        )
