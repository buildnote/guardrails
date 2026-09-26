#!/usr/bin/env python3
import posixpath

from guardrail import Guardrail

DEFAULT_PATHS = "CLAUDE.md,AGENTS.md"


def points_at(alias, link, target):
    return posixpath.normpath(posixpath.join(posixpath.dirname(alias), link)) == posixpath.normpath(target)


with Guardrail() as guardrail:
    paths = [it.strip() for it in guardrail.input("paths", DEFAULT_PATHS).split(",") if it.strip()]

    if len(paths) < 2:
        guardrail.skip("paths names '%s' rather than an alias and the file it stands for" % ",".join(paths))

    alias, target = paths[0], paths[1]
    files = guardrail.facts("files")["files"]

    if alias not in files or target not in files:
        guardrail.skip("neither %s nor %s was collected" % (alias, target))

    instructions = files[target]
    aliased = files[alias]

    if not instructions["present"]:
        guardrail.skip("%s is not there, so there is nothing for %s to stand for" % (target, alias))
    elif not aliased.get("symlink"):
        if aliased["present"]:
            guardrail.violation(
                aliased["location"],
                "%s is a file of its own rather than a symbolic link to %s, so the two drift apart"
                % (alias, target),
            )
        else:
            guardrail.violation(
                aliased["location"],
                "Claude Code reads no instructions here: %s is there and %s is not" % (target, alias),
            )
    elif not aliased["present"]:
        guardrail.violation(
            aliased["location"],
            "%s is a symbolic link to %s, which is not there" % (alias, aliased["symlinkTarget"]),
        )
    elif not points_at(alias, aliased["symlinkTarget"], target):
        guardrail.violation(
            aliased["location"],
            "%s is a symbolic link to %s rather than to %s" % (alias, aliased["symlinkTarget"], target),
        )
