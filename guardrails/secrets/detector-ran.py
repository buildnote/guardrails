#!/usr/bin/env python3
from guardrail import Guardrail

with Guardrail() as guardrail:
    secrets = guardrail.facts("secrets", "no secrets collector ran")

    if secrets.get("source") == "none":
        guardrail.violation(
            "no secret detector",
            "Nothing looked for a credential in this checkout: %s"
            % secrets.get("reason", "there was neither a report nor a detector")
        )
