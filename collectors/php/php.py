#!/usr/bin/env python3
import json
import os

from guardrail import Collector

MANIFEST = "composer.json"
LOCKFILE = "composer.lock"
SCOPES = ("require", "require-dev")
PLATFORM_PREFIXES = ("ext-", "lib-")
UNPINNED = ("^", "~", ">", "<", "*", "|", " ", "@", "!")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def pinned(constraint):
    if not constraint:
        return False
    if constraint.startswith("dev-") or constraint.endswith(".x-dev"):
        return False
    if any(marker in constraint for marker in UNPINNED):
        return False

    return constraint[0].isdigit() or constraint.startswith("v")


def platform(name):
    return any(name.startswith(prefix) for prefix in PLATFORM_PREFIXES)


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["type"] = None
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["platform"] = []
    collector.facts["scripts"] = []
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    text = read(os.path.join(project_dir, MANIFEST))
    if text is None:
        collector.nothing("no Composer project in %s" % project_dir)

    collector.facts["manifest"] = located(MANIFEST)

    try:
        document = json.loads(text)
    except ValueError as rejected:
        collector.facts["unparsed"].append({"path": located(MANIFEST), "reason": str(rejected)})
        collector.invalid("%s could not be read: %s" % (MANIFEST, rejected))

    if not isinstance(document, dict):
        collector.facts["unparsed"].append({"path": located(MANIFEST), "reason": "the manifest is not an object"})
        collector.invalid("%s is not an object" % MANIFEST)

    collector.facts["sources"] = [located(MANIFEST)]

    found = {}
    order = []
    requirements = []

    for scope in SCOPES:
        declared = document.get(scope)
        if not isinstance(declared, dict):
            continue
        for name, constraint in declared.items():
            if not isinstance(constraint, str):
                continue
            if platform(name):
                requirements.append({"name": name, "version": constraint})
                continue
            if name == "php":
                continue
            if name not in found:
                found[name] = {
                    "name": name,
                    "version": constraint,
                    "scopes": [],
                    "source": MANIFEST,
                    "pinned": pinned(constraint),
                }
                order.append(name)
            found[name]["scopes"].append(scope)

    config = document.get("config") if isinstance(document.get("config"), dict) else {}
    resolved = config.get("platform") if isinstance(config.get("platform"), dict) else {}
    constraint = resolved.get("php") if isinstance(resolved.get("php"), str) else None
    required = (document.get("require") or {}).get("php") if isinstance(document.get("require"), dict) else None

    if constraint and constraint.strip():
        collector.facts["declared"] = {"version": constraint.strip(), "source": MANIFEST, "pinned": pinned(constraint.strip())}
    elif isinstance(required, str) and required.strip():
        collector.facts["declared"] = {"version": required.strip(), "source": MANIFEST, "pinned": pinned(required.strip())}

    name = document.get("name")
    kind = document.get("type")
    scripts = document.get("scripts")

    dependencies = [found[it] for it in order]

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["type"] = kind if isinstance(kind, str) else None
    collector.facts["projects"] = [{
        "path": located("."),
        "manifest": located(MANIFEST),
        "name": name if isinstance(name, str) else None,
    }]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["platform"] = requirements
    collector.facts["scripts"] = sorted(scripts) if isinstance(scripts, dict) else []
    collector.facts["lockfiles"] = (
        [located(LOCKFILE)] if os.path.isfile(os.path.join(project_dir, LOCKFILE)) else []
    )
