#!/usr/bin/env python3
import glob
import os

import guardrail_toml
from guardrail import Collector

MANIFEST = "Cargo.toml"
LOCKFILE = "Cargo.lock"
TOOLCHAIN = "rust-toolchain.toml"
TOOLCHAIN_TEXT = "rust-toolchain"
CHANNELS = ("stable", "beta", "nightly")
SCOPES = ("dependencies", "dev-dependencies", "build-dependencies")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def parsed(project_dir, relative):
    text = read(os.path.join(project_dir, relative))

    if text is None:
        return None, "the manifest could not be read"

    reason = guardrail_toml.unsupported(text)

    return (None, reason) if reason else (guardrail_toml.parse(text), None)


def pinned(requirement):
    return bool(requirement) and requirement.strip().startswith("=")


def origin_of(declared):
    if not isinstance(declared, dict):
        return "registry"
    if declared.get("workspace") is True:
        return "workspace"
    if declared.get("path"):
        return "path"
    if declared.get("git"):
        return "git"

    return "registry"


def dependencies_in(document, source, scopes):
    found = {}
    order = []

    for scope in scopes:
        declared = document.get(scope)
        if not isinstance(declared, dict):
            continue
        for name, entry in declared.items():
            requirement = entry if isinstance(entry, str) else (entry.get("version") if isinstance(entry, dict) else None)
            if not isinstance(requirement, str):
                requirement = None
            if name not in found:
                found[name] = {
                    "name": name,
                    "version": requirement,
                    "scopes": [],
                    "source": source,
                    "pinned": pinned(requirement),
                    "origin": origin_of(entry),
                }
                order.append(name)
            found[name]["scopes"].append(scope)

    return [found[name] for name in order]


def members_of(document, project_dir, limit):
    workspace = document.get("workspace") if isinstance(document.get("workspace"), dict) else {}
    excluded = set(workspace.get("exclude") or [])
    found = []

    for member in workspace.get("members") or []:
        if not isinstance(member, str) or member in excluded:
            continue
        for path in sorted(glob.glob(os.path.join(project_dir, member, MANIFEST))):
            directory = os.path.relpath(os.path.dirname(path), project_dir).replace(os.sep, "/")
            if directory not in found:
                found.append(directory)

    return found[:limit], max(0, len(found) - limit)


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")
    limit = int(collector.input("maxMembers", "200") or 200)

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["edition"] = None
    collector.facts["workspace"] = False
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["lockfiles"] = []
    collector.facts["dropped"] = 0
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    if not os.path.isfile(os.path.join(project_dir, MANIFEST)):
        collector.nothing("no Cargo build in %s" % project_dir)

    collector.facts["manifest"] = located(MANIFEST)

    root, rejected = parsed(project_dir, MANIFEST)
    if root is None:
        collector.facts["unparsed"].append({"path": located(MANIFEST), "reason": rejected})
        collector.invalid("%s could not be read: %s" % (MANIFEST, rejected))

    package = root.get("package") if isinstance(root.get("package"), dict) else {}
    workspace = root.get("workspace") if isinstance(root.get("workspace"), dict) else None

    sources = [MANIFEST]
    projects = []
    dependencies = dependencies_in(root, MANIFEST, SCOPES)

    inherited = {}

    if workspace is not None:
        collector.facts["workspace"] = True
        dependencies += dependencies_in({"workspace": workspace.get("dependencies")}, MANIFEST, ["workspace"])
        if isinstance(workspace.get("package"), dict):
            inherited = workspace["package"]

    if package:
        name = package.get("name")
        projects.append({"path": ".", "manifest": MANIFEST, "name": name if isinstance(name, str) else None})
        edition = package.get("edition")
        collector.facts["edition"] = edition if isinstance(edition, str) else None
        constraint = package.get("rust-version")
        if isinstance(constraint, str) and constraint.strip():
            collector.facts["declared"] = {
                "version": constraint.strip(),
                "source": MANIFEST,
                "pinned": constraint.strip() not in CHANNELS,
            }

    if collector.facts["edition"] is None and isinstance(inherited.get("edition"), str):
        collector.facts["edition"] = inherited["edition"]

    if collector.facts["declared"] is None:
        constraint = inherited.get("rust-version")
        if isinstance(constraint, str) and constraint.strip():
            collector.facts["declared"] = {
                "version": constraint.strip(),
                "source": MANIFEST,
                "pinned": constraint.strip() not in CHANNELS,
            }

    members, dropped = members_of(root, project_dir, limit)

    if dropped:
        collector.log("%d workspace members were left out because maxMembers was reached" % dropped)

    collector.facts["dropped"] = dropped

    for directory in members:
        manifest = directory + "/" + MANIFEST
        document, rejected = parsed(project_dir, manifest)

        if document is None:
            projects.append({"path": directory, "manifest": manifest, "name": None})
            collector.facts["unparsed"].append({"path": located(manifest), "reason": rejected})
            continue

        declared = document.get("package") if isinstance(document.get("package"), dict) else {}
        sources.append(manifest)
        projects.append({
            "path": directory,
            "manifest": manifest,
            "name": declared.get("name") if isinstance(declared.get("name"), str) else None,
        })
        dependencies += dependencies_in(document, manifest, SCOPES)

        if collector.facts["edition"] is None and isinstance(declared.get("edition"), str):
            collector.facts["edition"] = declared["edition"]

    for name in (TOOLCHAIN, TOOLCHAIN_TEXT):
        text = read(os.path.join(project_dir, name))
        if not text or not text.strip():
            continue
        channel = text.strip()
        if name == TOOLCHAIN:
            document = guardrail_toml.parse(text)
            declared = (document or {}).get("toolchain") or {}
            channel = declared.get("channel") if isinstance(declared.get("channel"), str) else None
        if channel:
            collector.facts["declared"] = {
                "version": channel,
                "source": name,
                "pinned": not any(channel.startswith(it) for it in CHANNELS),
            }
            break

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]) if it["manifest"] else None,
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["lockfiles"] = (
        [located(LOCKFILE)] if os.path.isfile(os.path.join(project_dir, LOCKFILE)) else []
    )
