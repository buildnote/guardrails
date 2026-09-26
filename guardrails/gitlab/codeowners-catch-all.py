#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    codeowners = guardrail.facts("gitlab", "no gitlab collector ran").get("codeowners")
    patterns = [it.strip() for it in guardrail.input("patterns", "*,**,/*").split(",") if it.strip()]

    if codeowners is None:
        guardrail.skip("the repository carries no CODEOWNERS file")

    path = codeowners["path"]
    covering = [
        section for section in codeowners["sections"]
        if any(rule["pattern"] in patterns and rule["owners"] for rule in section["rules"])
    ]
    required = [section for section in covering if not section["optional"]]

    if not covering:
        guardrail.violation(
            path,
            "no section of %s declares an owned catch-all rule, so a path no section names is owned by nobody"
            % path,
        )
    elif not required:
        guardrail.violation(
            path,
            "the only owned catch-all rules in %s sit in optional sections (%s), whose approval GitLab never "
            "requires, so a path no other section names can merge unreviewed"
            % (path, ", ".join("[%s]" % section["name"] for section in covering)),
        )
