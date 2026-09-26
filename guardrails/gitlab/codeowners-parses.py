#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("gitlab", "no gitlab collector ran").get("codeowners")

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]

    for unparsed in codeowners.get("unparsed", []):
        guardrail.violation(
            "%s: %s" % (path, unparsed["line"]),
            "%s carries a line GitLab reads as neither a rule nor a section header: %s"
            % (path, unparsed["reason"]),
        )
