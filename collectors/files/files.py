#!/usr/bin/env python3
import os

from guardrail import Collector, slashed

DEFAULT_PATHS = "README.md,README.rst,LICENSE,LICENSE.md,CONTRIBUTING.md,CODE_OF_CONDUCT.md,SECURITY.md,.gitignore"


def described(path, location):
    described = {"present": os.path.isfile(path), "location": location}

    if os.path.islink(path):
        described["symlink"] = True
        described["symlinkTarget"] = slashed(os.readlink(path))

    if not described["present"]:
        return described

    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError as error:
        described["unreadable"] = str(error)
        return described

    described["bytes"] = os.path.getsize(path)
    described["lines"] = len(lines)
    described["nonBlankLines"] = sum(1 for line in lines if line.strip())

    return described


with Collector() as collector:
    requested = collector.input("paths", DEFAULT_PATHS).split(",") + [collector.input("path", "")]

    files = {}
    for path in requested:
        path = path.strip()
        if path and path not in files:
            files[path] = described(path, collector.path(path))

    collector.facts["files"] = files
