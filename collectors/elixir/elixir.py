#!/usr/bin/env python3
import os
import re

from guardrail import Collector

MANIFEST = "mix.exs"
LOCKFILE = "mix.lock"
DEFAULT_SCOPE = "default"
HEX_ORIGIN = "hex"
DEPENDENCY = re.compile(r"\{\s*:([A-Za-z_][A-Za-z0-9_]*)\s*,([^{}]*)\}")
REQUIREMENT = re.compile(r"^\s*\"([^\"]+)\"")
ONLY = re.compile(r"only:\s*(\[[^\]]*\]|:[A-Za-z_][A-Za-z0-9_]*)")
ATOM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
APP = re.compile(r"\bapp:\s*:([A-Za-z_][A-Za-z0-9_]*)")
VERSION = re.compile(r"\bversion:\s*\"([^\"]+)\"")
ELIXIR = re.compile(r"\belixir:\s*\"([^\"]+)\"")
APPS_PATH = re.compile(r"\bapps_path:\s*\"([^\"]+)\"")
UNPINNED = ("~", ">", "<", "*", "or", "and")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def uncommented(text):
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def pinned(requirement, options):
    if "git:" in options or "github:" in options or "path:" in options:
        return False
    if not requirement:
        return False

    return not any(marker in requirement for marker in UNPINNED)


def origin_of(options):
    if "git:" in options or "github:" in options:
        return "git"
    if "path:" in options:
        return "path"

    return HEX_ORIGIN


def scopes_in(options):
    found = ONLY.search(options)

    return ATOM.findall(found.group(1)) if found else [DEFAULT_SCOPE]


def dependencies_in(text, source):
    found = []

    for declared in DEPENDENCY.finditer(text):
        options = declared.group(2)
        requirement = REQUIREMENT.match(options)
        found.append({
            "name": declared.group(1),
            "version": requirement.group(1) if requirement else None,
            "scopes": scopes_in(options),
            "source": source,
            "pinned": pinned(requirement.group(1) if requirement else None, options),
            "origin": origin_of(options),
        })

    return found


def named(text, pattern):
    found = pattern.search(text)

    return found.group(1) if found else None


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["scanned"] = []
    collector.facts["declared"] = None
    collector.facts["app"] = None
    collector.facts["version"] = None
    collector.facts["umbrella"] = False
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    root = read(os.path.join(project_dir, MANIFEST))
    if root is None:
        collector.nothing("no Mix project in %s" % project_dir)

    collector.facts["manifest"] = MANIFEST

    body = uncommented(root)
    constraint = named(body, ELIXIR)
    apps_path = named(body, APPS_PATH)

    collector.facts["app"] = named(body, APP)
    collector.facts["version"] = named(body, VERSION)
    collector.facts["umbrella"] = apps_path is not None
    collector.facts["sources"] = [MANIFEST]
    collector.facts["scanned"] = [MANIFEST]

    if constraint:
        collector.facts["declared"] = {
            "version": constraint,
            "source": MANIFEST,
            "pinned": not any(marker in constraint for marker in UNPINNED),
        }

    projects = [{"path": ".", "manifest": MANIFEST, "name": collector.facts["app"]}]
    dependencies = dependencies_in(body, MANIFEST)

    if apps_path:
        directory = os.path.join(project_dir, apps_path)
        for name in sorted(os.listdir(directory) if os.path.isdir(directory) else []):
            manifest = apps_path + "/" + name + "/" + MANIFEST
            text = read(os.path.join(project_dir, manifest))
            if text is None:
                projects.append({"path": apps_path + "/" + name, "manifest": manifest, "name": None})
                collector.facts["unparsed"].append({"path": manifest, "reason": "the manifest could not be read"})
                continue
            nested = uncommented(text)
            collector.facts["sources"].append(manifest)
            collector.facts["scanned"].append(manifest)
            projects.append({"path": apps_path + "/" + name, "manifest": manifest, "name": named(nested, APP)})
            dependencies += dependencies_in(nested, manifest)

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["manifest"] = located(MANIFEST)
    collector.facts["sources"] = [located(it) for it in collector.facts["sources"]]
    collector.facts["scanned"] = [located(it) for it in collector.facts["scanned"]]
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]),
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["lockfiles"] = (
        [located(LOCKFILE)] if os.path.isfile(os.path.join(project_dir, LOCKFILE)) else []
    )
