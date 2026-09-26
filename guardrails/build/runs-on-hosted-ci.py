#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    env = guardrail.facts("env", "the CI environment was not collected")
    allow_self_hosted = guardrail.input("allowSelfHosted", "true").strip().lower() != "false"

    if not env.get("ci"):
        guardrail.violation(
            "provider=%s" % env.get("provider", "local"),
            "This build is not running on a CI runner, so nothing attributable produced it"
        )
    elif env.get("hosted") is False and not allow_self_hosted:
        guardrail.violation(
            "runner=%s" % (env.get("runner", {}).get("name") or "self hosted"),
            "This build ran on a self hosted runner, which this team does not trust to build a release"
        )
