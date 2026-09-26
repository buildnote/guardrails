#!/usr/bin/env python3
import re

from guardrail import Guardrail

CONTACT = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+|https?://\S+")

with Guardrail() as guardrail:
    path = guardrail.input("path", "SECURITY.md")
    min_lines = guardrail.number("minLines", 3)
    needs_contact = guardrail.input("contact", "true").strip().lower() != "false"
    files = guardrail.facts("files")["files"]

    described = files.get(path)

    if described is None:
        guardrail.skip("%s was not collected" % path)

    if not described["present"]:
        guardrail.violation(path, "No security policy at %s, so a reporter has nowhere to send a vulnerability" % path)
    elif "unreadable" in described:
        guardrail.skip("could not read %s: %s" % (path, described["unreadable"]))
    elif described["nonBlankLines"] < min_lines:
        guardrail.violation(
            "%s (%d non-blank lines)" % (path, described["nonBlankLines"]),
            "Security policy at %s has %d non-blank lines, fewer than the %d expected"
            % (path, described["nonBlankLines"], min_lines),
        )
    elif needs_contact:
        text = guardrail.read(path)

        if text is None:
            guardrail.skip("could not read %s" % path)
        elif not CONTACT.search(text):
            guardrail.violation(
                path,
                "Security policy at %s names no email address or URL to report a vulnerability to" % path,
            )
