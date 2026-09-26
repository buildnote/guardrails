#!/usr/bin/env python3
from guardrail import Guardrail


def year(edition):
    text = (edition or "").strip()

    return int(text) if text.isdigit() else None


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    min_edition = guardrail.number("minEdition", 2021)
    rust = guardrail.facts("rust", "no Cargo build in %s" % project_dir)

    if rust.get("incomplete"):
        guardrail.skip(rust["incomplete"])

    if not rust["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    edition = rust["edition"]
    read = ", ".join(rust["sources"]) or project_dir
    declared = year(edition)

    if not edition and rust["dropped"]:
        guardrail.skip(
            "%d workspace members were left out of the facts, so no manifest that was read declares an edition and "
            "one that was not read may" % rust["dropped"]
        )

    if not edition:
        guardrail.violation(
            read,
            "No Rust edition is declared in %s, so Cargo compiles the crate at the 2015 edition rather than one the "
            "build chose, under rules every edition since has changed" % read,
        )
    else:
        guardrail.log("%s declares the %s edition" % (read, edition))

        if declared is not None and declared < min_edition:
            guardrail.violation(
                "%s (edition %s)" % (read, edition),
                "The Cargo build in %s declares the %s edition, older than the %d expected, so the crate compiles "
                "under rules the language has moved on from" % (project_dir, edition, min_edition),
            )
