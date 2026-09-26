#!/usr/bin/env python3
import os

from guardrail import Collector

MODULE_MANIFEST = "go.mod"
WORKSPACE_MANIFEST = "go.work"
LOCKFILE = "go.sum"
DEFAULT_SCOPE = "default"
INDIRECT = "// indirect"
BLOCKS = ("require", "replace", "exclude", "retract", "use", "tool")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def uncommented(line):
    stripped = line.strip()

    return "" if stripped.startswith("//") else stripped


def directives(text):
    found = []
    block = None

    for line in text.splitlines():
        indirect = INDIRECT in line
        stripped = uncommented(line)
        if not stripped:
            continue

        body = stripped.split("//", 1)[0].strip()

        if block is not None:
            if body == ")":
                block = None
            elif body:
                found.append((block, body, indirect))
            continue

        name, _, rest = body.partition(" ")
        if name in BLOCKS and rest.strip() == "(":
            block = name
        elif name:
            found.append((name, rest.strip(), indirect))

    return found


def required(value):
    parts = value.split()

    return (parts[0], parts[1]) if len(parts) >= 2 else (parts[0], None) if parts else (None, None)


def replaced(value):
    left, arrow, right = value.partition("=>")

    if not arrow:
        return None

    return {"name": left.split()[0], "with": right.strip()} if left.split() and right.strip() else None


def module_in(text, source):
    declared = {"name": None, "version": None, "toolchain": None, "direct": [], "indirect": [], "replaced": []}

    for name, value, indirect in directives(text):
        if name == "module" and declared["name"] is None:
            declared["name"] = value.strip('"')
        elif name == "go" and declared["version"] is None:
            declared["version"] = value
        elif name == "toolchain" and declared["toolchain"] is None:
            declared["toolchain"] = value
        elif name == "require":
            path, version = required(value)
            if path is None:
                continue
            declared["indirect" if indirect else "direct"].append({
                "name": path,
                "version": version,
                "scopes": [DEFAULT_SCOPE],
                "source": source,
            })
        elif name == "replace":
            found = replaced(value)
            if found:
                found["source"] = source
                declared["replaced"].append(found)

    return declared


def uses(text):
    found = []

    for name, value, _ in directives(text):
        if name != "use":
            continue
        for entry in value.split():
            found.append(entry.strip('"'))

    return found


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["toolchain"] = None
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["replaced"] = []
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    workspace = read(os.path.join(project_dir, WORKSPACE_MANIFEST))
    root = read(os.path.join(project_dir, MODULE_MANIFEST))

    if workspace is None and root is None:
        collector.nothing("no Go module in %s" % project_dir)

    sources = []
    unparsed = []
    direct = []
    indirect = []
    replacements = []
    projects = []
    declared = None
    toolchain = None

    if workspace is not None:
        collector.facts["manifest"] = located(WORKSPACE_MANIFEST)
        sources.append(WORKSPACE_MANIFEST)
        members = uses(workspace)
        workspace_module = module_in(workspace, WORKSPACE_MANIFEST)
        declared = workspace_module["version"] and {
            "version": workspace_module["version"],
            "source": WORKSPACE_MANIFEST,
            "pinned": False,
        } or None
        toolchain = workspace_module["toolchain"]
        replacements += workspace_module["replaced"]
    else:
        collector.facts["manifest"] = located(MODULE_MANIFEST)
        members = ["."]

    if workspace is not None and root is not None and "." not in members:
        members = ["."] + members

    for member in members:
        directory = os.path.normpath(member).replace(os.sep, "/")
        manifest = MODULE_MANIFEST if directory == "." else directory + "/" + MODULE_MANIFEST
        text = read(os.path.join(project_dir, manifest))

        if text is None:
            projects.append({"path": directory, "manifest": None, "name": None})
            unparsed.append({"path": manifest, "reason": "no go.mod in the directory the workspace uses"})
            continue

        described = module_in(text, manifest)
        sources.append(manifest)
        projects.append({"path": directory, "manifest": manifest, "name": described["name"]})
        direct += described["direct"]
        indirect += described["indirect"]
        replacements += described["replaced"]

        if declared is None and described["version"]:
            declared = {"version": described["version"], "source": manifest, "pinned": False}

        if toolchain is None:
            toolchain = described["toolchain"]

        lockfile = LOCKFILE if directory == "." else directory + "/" + LOCKFILE
        if os.path.isfile(os.path.join(project_dir, lockfile)):
            collector.facts["lockfiles"].append(located(lockfile))

    for dependency in direct + indirect + replacements:
        dependency["source"] = located(dependency["source"])

    for entry in unparsed:
        entry["path"] = located(entry["path"])

    if declared:
        declared["source"] = located(declared["source"])

    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["declared"] = declared
    collector.facts["toolchain"] = toolchain
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]) if it["manifest"] else None,
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": direct, "transitive": indirect}
    collector.facts["replaced"] = replacements
    collector.facts["unparsed"] = unparsed
