#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    golang = guardrail.facts("golang", "no Go module in %s" % project_dir)

    if golang.get("incomplete"):
        guardrail.skip(golang["incomplete"])

    if not golang["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    toolchain = golang["toolchain"]
    manifest = golang["manifest"] or project_dir

    if not toolchain:
        guardrail.violation(
            manifest,
            "%s pins no toolchain, so the go directive is only a floor and the code is compiled by whichever Go the "
            "runner happens to carry" % manifest,
        )
    else:
        guardrail.log("%s selects %s" % (manifest, toolchain))
