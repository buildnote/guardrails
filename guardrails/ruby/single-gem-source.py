#!/usr/bin/env python3
from guardrail import Guardrail

DEFAULT_SOURCES = "https://rubygems.org"


def normalized(source):
    return source.strip().rstrip("/").lower()


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    ruby = guardrail.facts("ruby", "no Ruby project in %s" % project_dir)

    if ruby.get("incomplete"):
        guardrail.skip(ruby["incomplete"])

    if not ruby["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    manifest = ruby["manifest"] or project_dir
    declared = ruby["sources_declared"]
    allowed = [normalized(it) for it in guardrail.input("allowedSources", DEFAULT_SOURCES).split(",") if it.strip()]

    if not declared:
        guardrail.skip("%s names no gem source" % manifest)

    if not allowed:
        guardrail.log("no gem source is named as trusted, so only the number of sources is checked")

    if ruby["scanned"]:
        guardrail.log(
            "%s is Ruby read by pattern, so a source named inside a condition, a loop or an eval is not seen"
            % ", ".join(ruby["scanned"])
        )

    extra = declared[1:]
    untrusted = [it for it in declared if normalized(it) not in allowed] if allowed else []

    if extra:
        guardrail.violation(
            manifest,
            "%s resolves gems from %d sources (%s), so a gem published to more than one of them is installed from "
            "whichever offers the higher version, which is what a dependency confusion attack needs"
            % (manifest, len(declared), ", ".join(declared)),
        )

    for source in untrusted:
        guardrail.violation(
            "%s (%s)" % (manifest, source),
            "%s resolves gems from %s, which is not one of the sources this repository trusts (%s)"
            % (manifest, source, ", ".join(allowed)),
        )

    if not extra and not untrusted:
        guardrail.log("gems resolve from %s" % declared[0])
