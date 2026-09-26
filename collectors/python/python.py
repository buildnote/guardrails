#!/usr/bin/env python3
import configparser
import glob
import os
import re

import guardrail_toml
from guardrail import Collector

PYPROJECT = "pyproject.toml"
SETUP_CFG = "setup.cfg"
SETUP_PY = "setup.py"
PYTHON_VERSION = ".python-version"
LOCKFILES = ("poetry.lock", "uv.lock", "pdm.lock", "Pipfile.lock", "requirements.lock")
DEFAULT_SCOPE = "default"
DEFAULT_REQUIREMENTS = "requirements.txt,requirements-dev.txt,requirements/*.txt"
NAME = re.compile(r"^([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?\s*(.*)$")
NORMALISED = re.compile(r"[-_.]+")
OPTION = re.compile(r"^-")
UNPINNED = (">", "<", "~", "^", "*", "!")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def normalised(name):
    return NORMALISED.sub("-", name).lower()


def pinned(constraint):
    if not constraint:
        return False
    if any(marker in constraint for marker in UNPINNED) or "," in constraint:
        return False

    return constraint.strip().startswith("==")


def requirement(text, scope, source):
    body, _, marker = text.partition(";")
    found = NAME.match(body.strip())

    if not found:
        return None

    constraint = found.group(3).strip() or None

    return {
        "name": normalised(found.group(1)),
        "version": constraint,
        "scopes": [scope],
        "source": source,
        "pinned": pinned(constraint),
        "marker": marker.strip() or None,
    }


def requirements_in(entries, scope, source):
    found = []

    for entry in entries or []:
        if not isinstance(entry, str):
            continue
        declared = requirement(entry, scope, source)
        if declared:
            found.append(declared)

    return found


def poetry_in(declared, scope, source):
    found = []

    for name, constraint in (declared or {}).items():
        if name == "python":
            continue
        version = constraint if isinstance(constraint, str) else None
        if isinstance(constraint, dict):
            version = constraint.get("version")
        found.append({
            "name": normalised(name),
            "version": version,
            "scopes": [scope],
            "source": source,
            "pinned": bool(version) and not any(it in version for it in UNPINNED + (",",)),
            "marker": None,
        })

    return found


def lines_of(text):
    for line in (text or "").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped and not OPTION.match(stripped):
            yield stripped


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")
    patterns = [it.strip() for it in collector.input("requirements", DEFAULT_REQUIREMENTS).split(",") if it.strip()]

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["manifest"] = None
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["backend"] = None
    collector.facts["packaging"] = None
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["requirements"] = []
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    found = []
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(project_dir, pattern))):
            relative = os.path.relpath(path, project_dir).replace(os.sep, "/")
            if os.path.isfile(path) and relative not in found:
                found.append(relative)

    has_pyproject = os.path.isfile(os.path.join(project_dir, PYPROJECT))
    has_setup = os.path.isfile(os.path.join(project_dir, SETUP_CFG)) or os.path.isfile(os.path.join(project_dir, SETUP_PY))

    if not has_pyproject and not has_setup and not found:
        collector.nothing("no Python project in %s" % project_dir)

    sources = []
    dependencies = []
    projects = []
    document = None

    if has_pyproject:
        text = read(os.path.join(project_dir, PYPROJECT))
        reason = guardrail_toml.unsupported(text or "")
        document = None if reason else guardrail_toml.parse(text or "")

        if document is None:
            collector.facts["unparsed"].append({"path": PYPROJECT, "reason": reason or "unreadable"})
        else:
            sources.append(PYPROJECT)

    if document is not None:
        project = document.get("project") if isinstance(document.get("project"), dict) else {}
        tool = document.get("tool") if isinstance(document.get("tool"), dict) else {}
        poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
        build = document.get("build-system") if isinstance(document.get("build-system"), dict) else {}

        collector.facts["backend"] = build.get("build-backend") if isinstance(build.get("build-backend"), str) else None
        collector.facts["packaging"] = "pep621" if project else ("poetry" if poetry else None)

        name = project.get("name") or poetry.get("name")
        projects.append({
            "path": ".",
            "manifest": PYPROJECT,
            "name": name if isinstance(name, str) else None,
        })

        dependencies += requirements_in(project.get("dependencies"), DEFAULT_SCOPE, PYPROJECT)
        for extra, entries in (project.get("optional-dependencies") or {}).items():
            dependencies += requirements_in(entries, extra, PYPROJECT)

        dependencies += poetry_in(poetry.get("dependencies"), DEFAULT_SCOPE, PYPROJECT)
        for group, declared in (poetry.get("group") or {}).items():
            if isinstance(declared, dict):
                dependencies += poetry_in(declared.get("dependencies"), group, PYPROJECT)

        constraint = project.get("requires-python") or (poetry.get("dependencies") or {}).get("python")
        if isinstance(constraint, str) and constraint.strip():
            collector.facts["declared"] = {
                "version": constraint.strip(),
                "source": PYPROJECT,
                "pinned": pinned(constraint.strip()),
            }

        members = ((tool.get("uv") or {}).get("workspace") or {}).get("members")
        for member in members or []:
            if not isinstance(member, str):
                continue
            for path in sorted(glob.glob(os.path.join(project_dir, member, PYPROJECT))):
                directory = os.path.relpath(os.path.dirname(path), project_dir).replace(os.sep, "/")
                nested = guardrail_toml.parse(read(path) or "")
                declared = (nested or {}).get("project") or {}
                manifest = directory + "/" + PYPROJECT
                projects.append({
                    "path": directory,
                    "manifest": manifest,
                    "name": declared.get("name") if isinstance(declared.get("name"), str) else None,
                })
                if nested is None:
                    collector.facts["unparsed"].append({"path": manifest, "reason": "unreadable"})
                    continue
                sources.append(manifest)
                dependencies += requirements_in(declared.get("dependencies"), DEFAULT_SCOPE, manifest)

    if not projects and has_setup:
        manifest = SETUP_CFG if os.path.isfile(os.path.join(project_dir, SETUP_CFG)) else SETUP_PY
        collector.facts["packaging"] = "setuptools"
        name = None

        if manifest == SETUP_CFG:
            parser = configparser.ConfigParser()
            try:
                parser.read_string(read(os.path.join(project_dir, SETUP_CFG)) or "")
                sources.append(SETUP_CFG)
                name = parser.get("metadata", "name", fallback=None)
                dependencies += requirements_in(
                    (parser.get("options", "install_requires", fallback="") or "").split("\n"),
                    DEFAULT_SCOPE,
                    SETUP_CFG,
                )
                constraint = parser.get("options", "python_requires", fallback=None)
                if constraint and constraint.strip():
                    collector.facts["declared"] = {
                        "version": constraint.strip(),
                        "source": SETUP_CFG,
                        "pinned": pinned(constraint.strip()),
                    }
            except configparser.Error as rejected:
                collector.facts["unparsed"].append({"path": SETUP_CFG, "reason": str(rejected).splitlines()[0]})
        else:
            collector.facts["unparsed"].append({
                "path": SETUP_PY,
                "reason": "setup.py is Python rather than a declaration and is not read",
            })

        projects.append({"path": ".", "manifest": manifest, "name": name})

    for relative in found:
        text = read(os.path.join(project_dir, relative))
        if text is None:
            collector.facts["unparsed"].append({"path": relative, "reason": "the file could not be read"})
            continue
        collector.facts["requirements"].append(relative)
        sources.append(relative)
        scope = os.path.basename(relative).rsplit(".", 1)[0]
        for line in lines_of(text):
            declared = requirement(line, scope, relative)
            if declared:
                dependencies.append(declared)

    if not projects:
        collector.facts["packaging"] = "requirements"

    text = read(os.path.join(project_dir, PYTHON_VERSION))
    if text and text.strip():
        collector.facts["declared"] = {
            "version": text.strip(),
            "source": PYTHON_VERSION,
            "pinned": not any(it in text.strip() for it in UNPINNED),
        }

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    collector.facts["requirements"] = [located(it) for it in collector.facts["requirements"]]
    collector.facts["manifest"] = located(sources[0]) if sources else None
    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]) if it["manifest"] else None,
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["lockfiles"] = [
        located(it) for it in LOCKFILES if os.path.isfile(os.path.join(project_dir, it))
    ]
