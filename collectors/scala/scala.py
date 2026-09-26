#!/usr/bin/env python3
import os
import re

from guardrail import Collector

MANIFEST = "build.sbt"
PROPERTIES = "project/build.properties"
PLUGINS = "project/plugins.sbt"
LOCKFILES = ("build.sbt.lock", "sbt.lock")
DEFAULT_SCOPE = "default"
DEPENDENCY = re.compile(
    r"\"([A-Za-z0-9_.\-]+)\"\s*(%%?)\s*\"([A-Za-z0-9_.\-]+)\"\s*%\s*(\"[^\"]*\"|[A-Za-z_][A-Za-z0-9_.]*)"
    r"(\s*%\s*(?:\"[^\"]*\"|[A-Za-z_][A-Za-z0-9_.]*))?"
)
SCALA_VERSION = re.compile(r"\bscalaVersion\s*(?::=|\+=)\s*\"([^\"]+)\"")
SBT_VERSION = re.compile(r"^\s*sbt\.version\s*=\s*(\S+)", re.M)
SUBPROJECT = re.compile(r"\blazy\s+val\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(\s*)?project(?:\s*\)?)?(?:[^\n]*?\bfile\(\s*\"([^\"]*)\"\s*\))?")
MOVING = ("latest.", "+", "[", "(")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def uncommented(text):
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    return "\n".join(line.split("//", 1)[0] for line in without_blocks.splitlines())


def literal(text):
    return text.startswith("\"") and text.endswith("\"")


def dependencies_in(text, source):
    found = []

    for declared in DEPENDENCY.finditer(text):
        revision = declared.group(4)
        configuration = declared.group(5)
        version = revision.strip("\"") if literal(revision) else None
        scope = DEFAULT_SCOPE

        if configuration:
            named = configuration.split("%", 1)[-1].strip()
            scope = named.strip("\"") or DEFAULT_SCOPE

        found.append({
            "name": declared.group(1) + ":" + declared.group(3),
            "version": version,
            "scopes": [scope],
            "source": source,
            "pinned": bool(version) and not any(marker in version for marker in MOVING),
            "crossVersion": declared.group(2) == "%%",
        })

    return found


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
    collector.facts["sbt"] = None
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["plugins"] = []
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    root = read(os.path.join(project_dir, MANIFEST))
    properties = read(os.path.join(project_dir, PROPERTIES))

    if root is None and properties is None:
        collector.nothing("no sbt build in %s" % project_dir)

    sources = []
    projects = [{"path": ".", "manifest": MANIFEST, "name": None}]
    dependencies = []

    if root is None:
        collector.facts["unparsed"].append({"path": MANIFEST, "reason": "the build file could not be read"})
    else:
        body = uncommented(root)
        sources.append(MANIFEST)
        collector.facts["scanned"].append(MANIFEST)
        dependencies += dependencies_in(body, MANIFEST)

        found = SCALA_VERSION.search(body)
        if found:
            collector.facts["declared"] = {"version": found.group(1), "source": MANIFEST, "pinned": True}

        for declared in SUBPROJECT.finditer(body):
            directory = declared.group(2) or declared.group(1)
            projects.append({
                "path": directory.strip("./") or ".",
                "manifest": MANIFEST,
                "name": declared.group(1),
            })

    if properties is not None:
        sources.append(PROPERTIES.replace(os.sep, "/"))
        found = SBT_VERSION.search(properties)
        collector.facts["sbt"] = found.group(1) if found else None

    plugins = read(os.path.join(project_dir, PLUGINS))
    if plugins is not None:
        relative = PLUGINS.replace(os.sep, "/")
        sources.append(relative)
        collector.facts["scanned"].append(relative)
        collector.facts["plugins"] = [it["name"] for it in dependencies_in(uncommented(plugins), relative)]

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["manifest"] = located(MANIFEST)
    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["scanned"] = [located(it) for it in collector.facts["scanned"]]
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]),
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["lockfiles"] = [
        located(it) for it in LOCKFILES if os.path.isfile(os.path.join(project_dir, it))
    ]
