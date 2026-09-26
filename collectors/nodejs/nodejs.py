#!/usr/bin/env python3
import glob
import json
import os

from guardrail import Collector

MANIFEST = "package.json"
NVMRC = ".nvmrc"
NODE_VERSION = ".node-version"
LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb")
SCOPES = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
UNPINNED = ("^", "~", ">", "<", "=", "|", " ", "*", "x", "X")
PROTOCOLS = ("workspace:", "npm:", "file:", "link:", "git+", "github:", "http:", "https:")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def manifest_in(project_dir, path):
    text = read(os.path.join(project_dir, path))

    if text is None:
        return None, "the manifest could not be read"

    try:
        document = json.loads(text)
    except ValueError as rejected:
        return None, str(rejected)

    if not isinstance(document, dict):
        return None, "the manifest is not an object"

    return document, None


def pinned(constraint):
    if not constraint or any(constraint.startswith(protocol) for protocol in PROTOCOLS):
        return False
    if any(marker in constraint for marker in UNPINNED):
        return False

    return constraint[0].isdigit()


def dependencies_in(document, source):
    found = {}
    order = []

    for scope in SCOPES:
        declared = document.get(scope)
        if not isinstance(declared, dict):
            continue
        for name, constraint in declared.items():
            if not isinstance(constraint, str):
                continue
            if name not in found:
                found[name] = {
                    "name": name,
                    "version": constraint,
                    "scopes": [],
                    "source": source,
                    "pinned": pinned(constraint),
                }
                order.append(name)
            found[name]["scopes"].append(scope)

    return [found[name] for name in order]


def workspaces_in(document):
    declared = document.get("workspaces")

    if isinstance(declared, dict):
        declared = declared.get("packages")

    if not isinstance(declared, list):
        return []

    return [it for it in declared if isinstance(it, str)]


def resolved(project_dir, patterns, limit):
    found = []

    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(project_dir, pattern, MANIFEST))):
            directory = os.path.relpath(os.path.dirname(path), project_dir).replace(os.sep, "/")
            if directory not in found:
                found.append(directory)

    return found[:limit], max(0, len(found) - limit)


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")
    limit = int(collector.input("maxWorkspaces", "200") or 200)

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["packageManager"] = None
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["scripts"] = []
    collector.facts["lockfiles"] = []
    collector.facts["dropped"] = 0
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    if not os.path.isfile(os.path.join(project_dir, MANIFEST)):
        collector.nothing("no Node.js project in %s" % project_dir)

    collector.facts["manifest"] = located(MANIFEST)

    root, rejected = manifest_in(project_dir, MANIFEST)
    if root is None:
        collector.facts["unparsed"].append({"path": located(MANIFEST), "reason": rejected})
        collector.invalid("%s could not be read: %s" % (MANIFEST, rejected))

    sources = [MANIFEST]
    dependencies = dependencies_in(root, MANIFEST)
    projects = [{"path": ".", "manifest": MANIFEST, "name": root.get("name") if isinstance(root.get("name"), str) else None}]

    members, dropped = resolved(project_dir, workspaces_in(root), limit)

    if dropped:
        collector.log("%d workspace packages were left out because maxWorkspaces was reached" % dropped)

    collector.facts["dropped"] = dropped

    for directory in members:
        manifest = directory + "/" + MANIFEST
        document, rejected = manifest_in(project_dir, manifest)

        if document is None:
            projects.append({"path": directory, "manifest": manifest, "name": None})
            collector.facts["unparsed"].append({"path": located(manifest), "reason": rejected})
            continue

        sources.append(manifest)
        projects.append({
            "path": directory,
            "manifest": manifest,
            "name": document.get("name") if isinstance(document.get("name"), str) else None,
        })
        dependencies += dependencies_in(document, manifest)

    engines = root.get("engines")
    engine = engines.get("node") if isinstance(engines, dict) else None
    for name in (NVMRC, NODE_VERSION):
        text = read(os.path.join(project_dir, name))
        if text and text.strip():
            collector.facts["declared"] = {
                "version": text.strip(),
                "source": located(name),
                "pinned": pinned(text.strip().lstrip("v")),
            }
            break

    if collector.facts["declared"] is None and isinstance(engine, str) and engine.strip():
        collector.facts["declared"] = {
            "version": engine.strip(),
            "source": located(MANIFEST),
            "pinned": pinned(engine.strip()),
        }

    manager = root.get("packageManager")
    scripts = root.get("scripts")

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["packageManager"] = manager if isinstance(manager, str) else None
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]) if it["manifest"] else None,
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["scripts"] = sorted(scripts) if isinstance(scripts, dict) else []
    collector.facts["lockfiles"] = [
        located(it) for it in LOCKFILES if os.path.isfile(os.path.join(project_dir, it))
    ]
