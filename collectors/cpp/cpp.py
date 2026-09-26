#!/usr/bin/env python3
import json
import os
import re

from guardrail import Collector

CMAKE = "CMakeLists.txt"
VCPKG = "vcpkg.json"
CONAN_TXT = "conanfile.txt"
CONAN_PY = "conanfile.py"
MESON = "meson.build"
BAZEL = "MODULE.bazel"
MAKEFILE = "Makefile"
LOCKFILES = ("conan.lock", "vcpkg-lock.json")
DEFAULT_SCOPE = "default"
MINIMUM = re.compile(r"cmake_minimum_required\s*\(\s*VERSION\s+([0-9][0-9.]*)", re.I)
STANDARD = re.compile(r"set\s*\(\s*CMAKE_CXX_STANDARD\s+([0-9]+)", re.I)
REQUIRED = re.compile(r"set\s*\(\s*CMAKE_CXX_STANDARD_REQUIRED\s+(\w+)", re.I)
PROJECT = re.compile(r"^\s*project\s*\(\s*([A-Za-z0-9_.\-]+)", re.I | re.M)
PROJECT_CALL = re.compile(r"^\s*project\s*\(([^)]*)\)", re.I | re.M)
QUOTED = re.compile(r'"[^"]*"')
LANGUAGES = ("C", "CXX", "CUDA", "OBJC", "OBJCXX", "FORTRAN", "HIP", "ISPC", "ASM", "NONE")
FIND_PACKAGE = re.compile(r"find_package\s*\(\s*([A-Za-z0-9_.\-]+)", re.I)
REQUIRE = re.compile(r"^([A-Za-z0-9_.+\-]+)/([^\s@#]+)")
TRUTHS = ("on", "true", "yes", "1")


def languages_in(body):
    found = []

    for call in PROJECT_CALL.finditer(body):
        for token in QUOTED.sub(" ", call.group(1)).split()[1:]:
            language = token.strip().upper()
            if language in LANGUAGES and language not in found:
                found.append(language)

    return found


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def uncommented(text):
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def sections_of(text):
    found = {}
    section = None

    for line in uncommented(text).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            found.setdefault(section, [])
            continue
        if section is not None:
            found[section].append(stripped)

    return found


def vcpkg_in(entries, scope, source):
    found = []

    for entry in entries or []:
        name = entry if isinstance(entry, str) else (entry.get("name") if isinstance(entry, dict) else None)
        if not isinstance(name, str):
            continue
        version = entry.get("version>=") if isinstance(entry, dict) else None
        found.append({
            "name": name,
            "version": version if isinstance(version, str) else None,
            "scopes": [scope],
            "source": source,
            "pinned": False,
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
    collector.facts["buildSystem"] = None
    collector.facts["packageManager"] = None
    collector.facts["declared"] = None
    collector.facts["cmakeMinimum"] = None
    collector.facts["baseline"] = None
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["findPackages"] = []
    collector.facts["languages"] = []
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    def there(name):
        return os.path.isfile(os.path.join(project_dir, name))

    cmake = read(os.path.join(project_dir, CMAKE))
    vcpkg = read(os.path.join(project_dir, VCPKG))
    conan_txt = read(os.path.join(project_dir, CONAN_TXT))
    conan_py = read(os.path.join(project_dir, CONAN_PY))

    if cmake is None and vcpkg is None and conan_txt is None and conan_py is None:
        collector.nothing("no C or C++ build in %s" % project_dir)

    collector.facts["buildSystem"] = (
        "cmake" if cmake is not None else
        "meson" if there(MESON) else
        "bazel" if there(BAZEL) else
        "make" if there(MAKEFILE) else None
    )
    has_conan = conan_txt is not None or conan_py is not None
    collector.facts["packageManager"] = (
        "both" if vcpkg is not None and has_conan else
        "vcpkg" if vcpkg is not None else
        "conan" if has_conan else None
    )

    sources = []
    projects = []
    dependencies = []

    if cmake is not None:
        body = uncommented(cmake)
        sources.append(CMAKE)
        collector.facts["scanned"].append(CMAKE)

        minimum = MINIMUM.search(body)
        collector.facts["cmakeMinimum"] = minimum.group(1) if minimum else None

        standard = STANDARD.search(body)
        if standard:
            required = REQUIRED.search(body)
            collector.facts["declared"] = {
                "version": standard.group(1),
                "source": CMAKE,
                "pinned": bool(required) and required.group(1).strip().lower() in TRUTHS,
            }

        for declared in PROJECT.finditer(body):
            projects.append({"path": ".", "manifest": CMAKE, "name": declared.group(1)})

        collector.facts["findPackages"] = sorted(set(FIND_PACKAGE.findall(body)))
        collector.facts["languages"] = languages_in(body)

    if vcpkg is not None:
        try:
            document = json.loads(vcpkg)
        except ValueError as rejected:
            collector.facts["unparsed"].append({"path": VCPKG, "reason": str(rejected)})
            document = None

        if isinstance(document, dict):
            sources.append(VCPKG)
            baseline = document.get("builtin-baseline")
            collector.facts["baseline"] = baseline if isinstance(baseline, str) else None
            name = document.get("name")
            if isinstance(name, str) and not projects:
                projects.append({"path": ".", "manifest": VCPKG, "name": name})
            dependencies += vcpkg_in(document.get("dependencies"), DEFAULT_SCOPE, VCPKG)
            features = document.get("features") if isinstance(document.get("features"), dict) else {}
            for feature in sorted(features):
                declared = features[feature] if isinstance(features[feature], dict) else {}
                dependencies += vcpkg_in(declared.get("dependencies"), feature, VCPKG)

    if conan_txt is not None:
        sources.append(CONAN_TXT)
        sections = sections_of(conan_txt)
        for section, scope in (("requires", DEFAULT_SCOPE), ("tool_requires", "build"), ("test_requires", "test")):
            for line in sections.get(section, []):
                found = REQUIRE.match(line)
                if not found:
                    continue
                dependencies.append({
                    "name": found.group(1),
                    "version": found.group(2),
                    "scopes": [scope],
                    "source": CONAN_TXT,
                    "pinned": "[" not in found.group(2),
                })

    if conan_py is not None:
        sources.append(CONAN_PY)
        collector.facts["scanned"].append(CONAN_PY)

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["manifest"] = located(sources[0]) if sources else None
    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["scanned"] = [located(it) for it in collector.facts["scanned"]]
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]),
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
    collector.facts["lockfiles"] = [located(it) for it in LOCKFILES if there(it)]
