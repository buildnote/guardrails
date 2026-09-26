#!/usr/bin/env python3
import json
import os
import xml.etree.ElementTree as ElementTree

from guardrail import Collector

GLOBAL_JSON = "global.json"
CENTRAL = "Directory.Packages.props"
LOCKFILE = "packages.lock.json"
PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
SOLUTION_SUFFIXES = (".sln", ".slnx")
SKIPPED = {".git", "bin", "obj", "node_modules", ".vs", "packages"}
DEFAULT_SCOPE = "default"
DEVELOPMENT_SCOPE = "development"
UNPINNED = ("*", "[", "(", "$")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def tag_of(element):
    return element.tag.split("}")[-1]


def parse(path):
    try:
        return ElementTree.parse(path).getroot(), None
    except ElementTree.ParseError as rejected:
        return None, str(rejected)
    except OSError:
        return None, "the file could not be read"


def attribute(element, name):
    for key, value in element.attrib.items():
        if key.split("}")[-1].lower() == name.lower():
            return value

    return None


def property_of(root, name):
    for group in root:
        if tag_of(group) != "PropertyGroup":
            continue
        for entry in group:
            if tag_of(entry) == name and entry.text:
                return entry.text.strip()

    return None


def frameworks_of(root):
    single = property_of(root, "TargetFramework")
    several = property_of(root, "TargetFrameworks")
    found = [single] if single else []

    for name in (several or "").split(";"):
        if name.strip():
            found.append(name.strip())

    return [it for it in found if "$" not in it]


def pinned(version):
    return bool(version) and not any(marker in version for marker in UNPINNED)


def references_of(root, source, central):
    found = []

    for group in root:
        if tag_of(group) != "ItemGroup":
            continue
        for entry in group:
            if tag_of(entry) != "PackageReference":
                continue
            name = attribute(entry, "Include") or attribute(entry, "Update")
            if not name:
                continue
            version = attribute(entry, "Version")
            managed = None
            if version is None:
                for nested in entry:
                    if tag_of(nested) == "Version" and nested.text:
                        version = nested.text.strip()
            if version is None and name in central:
                version = central[name]
                managed = CENTRAL
            assets = attribute(entry, "PrivateAssets") or ""
            found.append({
                "name": name,
                "version": version,
                "scopes": [DEVELOPMENT_SCOPE if assets.strip().lower() == "all" else DEFAULT_SCOPE],
                "source": source,
                "pinned": pinned(version),
                "managedBy": managed,
            })

    return found


def versions_of(root):
    found = {}

    for group in root:
        if tag_of(group) != "ItemGroup":
            continue
        for entry in group:
            if tag_of(entry) != "PackageVersion":
                continue
            name = attribute(entry, "Include")
            version = attribute(entry, "Version")
            if name and version:
                found[name] = version

    return found


def walk(project_dir, limit):
    projects = []
    solutions = []
    lockfiles = []

    for root, directories, names in os.walk(project_dir):
        directories[:] = sorted(it for it in directories if it not in SKIPPED)
        for name in sorted(names):
            relative = os.path.relpath(os.path.join(root, name), project_dir).replace(os.sep, "/")
            if name.endswith(PROJECT_SUFFIXES):
                projects.append(relative)
            elif name.endswith(SOLUTION_SUFFIXES):
                solutions.append(relative)
            elif name == LOCKFILE:
                lockfiles.append(relative)

    found = sorted(projects)

    return found[:limit], max(0, len(found) - limit), sorted(solutions), sorted(lockfiles)


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")
    limit = int(collector.input("maxProjects", "200") or 200)

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["rollForward"] = None
    collector.facts["targetFrameworks"] = []
    collector.facts["solution"] = None
    collector.facts["centralPackageManagement"] = False
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["lockfiles"] = []
    collector.facts["dropped"] = 0
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    found, dropped, solutions, lockfiles = walk(project_dir, limit)

    if dropped:
        collector.log("%d project files were left out because maxProjects was reached" % dropped)

    collector.facts["dropped"] = dropped

    if not found and not solutions:
        collector.nothing("no .NET project in %s" % project_dir)

    sources = []
    central = {}

    if os.path.isfile(os.path.join(project_dir, CENTRAL)):
        root, rejected = parse(os.path.join(project_dir, CENTRAL))
        if root is None:
            collector.facts["unparsed"].append({"path": CENTRAL, "reason": rejected})
        else:
            collector.facts["centralPackageManagement"] = property_of(root, "ManagePackageVersionsCentrally") != "false"
            central = versions_of(root)
            sources.append(CENTRAL)

    text = read(os.path.join(project_dir, GLOBAL_JSON))
    if text is not None:
        try:
            document = json.loads(text)
        except ValueError as rejected:
            collector.facts["unparsed"].append({"path": GLOBAL_JSON, "reason": str(rejected)})
            document = None
        if isinstance(document, dict):
            sources.append(GLOBAL_JSON)
            sdk = document.get("sdk") if isinstance(document.get("sdk"), dict) else {}
            forward = sdk.get("rollForward") if isinstance(sdk.get("rollForward"), str) else None
            version = sdk.get("version") if isinstance(sdk.get("version"), str) else None
            collector.facts["rollForward"] = forward
            if version:
                collector.facts["declared"] = {
                    "version": version,
                    "source": GLOBAL_JSON,
                    "pinned": forward in (None, "disable"),
                }

    projects = []
    dependencies = []
    frameworks = set()

    for relative in found:
        root, rejected = parse(os.path.join(project_dir, relative))
        directory = os.path.dirname(relative) or "."

        if root is None:
            projects.append({"path": directory, "manifest": relative, "name": None, "targetFrameworks": []})
            collector.facts["unparsed"].append({"path": relative, "reason": rejected})
            continue

        declared = frameworks_of(root)
        frameworks.update(declared)
        sources.append(relative)
        projects.append({
            "path": directory,
            "manifest": relative,
            "name": property_of(root, "AssemblyName") or os.path.basename(relative).rsplit(".", 1)[0],
            "targetFrameworks": declared,
        })
        dependencies += references_of(root, relative, central)

    manifest = solutions[0] if solutions else (found[0] if found else None)

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["solution"] = located(solutions[0]) if solutions else None
    collector.facts["manifest"] = located(manifest) if manifest else None
    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["targetFrameworks"] = sorted(frameworks)
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]) if it["manifest"] else None,
        "name": it["name"],
        "targetFrameworks": it["targetFrameworks"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["lockfiles"] = [located(it) for it in lockfiles]
