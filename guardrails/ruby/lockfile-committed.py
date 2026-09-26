#!/usr/bin/env python3
import os

from guardrail import Guardrail

GEMFILE = "Gemfile"

with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    ruby = guardrail.facts("ruby", "no Ruby project in %s" % project_dir)

    if ruby.get("incomplete"):
        guardrail.skip(ruby["incomplete"])

    if not ruby["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if not any(os.path.basename(it) == GEMFILE for it in ruby["sources"]):
        guardrail.skip("no Gemfile in %s, so Bundler has nothing to resolve or lock" % project_dir)

    lockfiles = sorted(ruby["lockfiles"])

    if not lockfiles:
        guardrail.violation(
            ruby["manifest"] or project_dir,
            "The Bundler project in %s commits no Gemfile.lock, so an install of this commit resolves whichever "
            "gem versions RubyGems serves that day rather than the ones that were reviewed" % project_dir,
        )
    else:
        locked = ", ".join(lockfiles)

        if ruby["bundler"]:
            locked = "%s, written by Bundler %s" % (locked, ruby["bundler"])

        guardrail.log("locked by %s" % locked)
