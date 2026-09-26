#!/usr/bin/env python3
import os
import re

from guardrail import Collector, slashed

MANIFESTS = ["build.gradle.kts", "build.gradle"]
SETTINGS = ["settings.gradle.kts", "settings.gradle"]
WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"
VERSION_CATALOG = "gradle/libs.versions.toml"
LOCKFILE = "gradle.lockfile"
DEPENDENCY_LOCKS = "gradle/dependency-locks"

INCLUDE = re.compile(r"""^\s*include\s*(?:\(|["'])""")
QUOTED = re.compile(r"""["']([^"']+)["']""")
DEPENDENCIES = re.compile(r"""(?m)^[ \t]*dependencies\s*\{""")
CONSTRAINTS = re.compile(r"""(?m)^[ \t]*constraints\s*\{""")
WRAPPED = r"""(?:(?P<wrapper>platform|enforcedPlatform|testFixtures)\s*\(\s*)?"""
DECLARATION = r"""^\s*(?P<configuration>[A-Za-z][A-Za-z0-9_]*)\s*(?:\(\s*)?"""
COORDINATE = re.compile(DECLARATION + WRAPPED + r"""["'](?P<coordinate>[^"']+)["']""")
ALIAS = re.compile(DECLARATION + WRAPPED + r"""libs\.(?P<alias>[A-Za-z0-9._]+)""")
PLATFORMS = ["platform", "enforcedPlatform"]
NAMED = re.compile(
    r"""^\s*([A-Za-z][A-Za-z0-9_]*)\s+group\s*:\s*["']([^"']+)["']\s*,\s*name\s*:\s*["']([^"']+)["']"""
    r"""(?:\s*,\s*version\s*:\s*["']([^"']+)["'])?"""
)
MODULE = re.compile(r"""module\s*=\s*["']([^"']+)["']""")
GROUP = re.compile(r"""group\s*=\s*["']([^"']+)["']""")
NAME = re.compile(r"""\bname\s*=\s*["']([^"']+)["']""")
VERSION_REF = re.compile(r"""version\.ref\s*=\s*["']([^"']+)["']""")
VERSION = re.compile(r"""version\s*=\s*["']([^"']+)["']""")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def manifest_in(directory):
    for name in MANIFESTS:
        if os.path.isfile(os.path.join(directory, name)):
            return name

    return None


def relative(prefix, name):
    return slashed(os.path.normpath(os.path.join(prefix, name))) if prefix else name


def beside(prefix, directory, names):
    if not directory:
        return None

    for name in names:
        if os.path.isfile(os.path.join(directory, name)):
            return relative(prefix, name)

    return None


def sections_in(text):
    sections = {}
    section = None
    pending = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not pending:
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("["):
                section = stripped.strip("[]")
                continue
            if section is None or "=" not in stripped:
                continue
        pending = (pending + " " + stripped).strip()
        if pending.count("{") != pending.count("}"):
            continue
        sections.setdefault(section, []).append(pending)
        pending = ""

    return sections


def versions_in(sections):
    versions = {}
    for entry in sections.get("versions", []):
        name, _, value = entry.partition("=")
        quoted = QUOTED.search(value)
        if quoted:
            versions[name.strip()] = quoted.group(1)

    return versions


def libraries_in(sections, versions):
    libraries = {}
    for entry in sections.get("libraries", []):
        alias, _, value = entry.partition("=")
        library = library_in(value.strip(), versions)
        if library:
            libraries[alias.strip().replace("-", ".").replace("_", ".")] = library

    return libraries


def library_in(value, versions):
    if value.startswith('"') or value.startswith("'"):
        quoted = QUOTED.search(value)

        return coordinate_in(quoted.group(1)) if quoted else None

    module = MODULE.search(value)
    if module:
        found = coordinate_in(module.group(1))
        group, name = (found[0], found[1]) if found else (None, None)
    else:
        declared_group = GROUP.search(value)
        declared_name = NAME.search(value)
        group = declared_group.group(1) if declared_group else None
        name = declared_name.group(1) if declared_name else None

    if not group or not name:
        return None

    reference = VERSION_REF.search(value)
    literal = VERSION.search(value)
    if reference:
        return group, name, versions.get(reference.group(1))

    return group, name, literal.group(1) if literal else None


def coordinate_in(text):
    parts = text.split(":")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None

    return parts[0], parts[1], parts[2] if len(parts) > 2 else None


def uncommented(text):
    kept = []
    index = 0
    quote = None
    while index < len(text):
        character = text[index]
        if quote:
            kept.append(character)
            if character == "\\" and index + 1 < len(text):
                kept.append(text[index + 1])
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
        elif character in "\"'":
            quote = character
            kept.append(character)
            index += 1
        elif text.startswith("//", index):
            while index < len(text) and text[index] != "\n":
                index += 1
        elif text.startswith("/*", index):
            closing = text.find("*/", index)
            index = len(text) if closing < 0 else closing + 2
        else:
            kept.append(character)
            index += 1

    return "".join(kept)


def blocks_of(pattern, text):
    blocks = []
    for found in pattern.finditer(text):
        opening = found.end() - 1
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append((found.start(), index + 1, text[opening + 1:index]))
                    break

    return blocks


def without(pattern, text):
    for start, end, _ in reversed(blocks_of(pattern, text)):
        text = text[:start] + text[end:]

    return text


def blocks_in(text):
    return [without(CONSTRAINTS, block) for _, _, block in blocks_of(DEPENDENCIES, uncommented(text))]


def declaration_in(line, libraries, source):
    named = NAMED.match(line)
    if named:
        return entry(named.group(1), (named.group(2), named.group(3), named.group(4)), None, source)

    coordinate = COORDINATE.match(line)
    if coordinate:
        return entry(
            coordinate.group("configuration"),
            coordinate_in(coordinate.group("coordinate")),
            coordinate.group("wrapper"),
            source,
        )

    alias = ALIAS.match(line)
    if alias:
        return entry(
            alias.group("configuration"),
            libraries.get(alias.group("alias")),
            alias.group("wrapper"),
            source,
        )

    return None


def entry(configuration, coordinate, wrapper, source):
    if coordinate is None:
        return None

    group, name, version = coordinate
    if "$" in group or "$" in name:
        return None

    declared = {
        "path": group + ":" + name,
        "version": None if version and "$" in version else version,
        "scopes": [configuration],
        "source": source,
    }
    if wrapper in PLATFORMS:
        declared["platform"] = True

    return declared


def declared_in(text, libraries, source):
    return [
        declaration for block in blocks_in(text)
        for declaration in (declaration_in(line, libraries, source) for line in block.splitlines())
        if declaration
    ]


def included_in(text):
    paths = []
    for line in text.splitlines():
        if not INCLUDE.match(line):
            continue
        for quoted in QUOTED.findall(line):
            path = ":" + quoted.strip(":")
            if "$" in path or path in paths:
                continue
            paths.append(path)

    return paths


def lockfiles_in(directory):
    found = []
    if os.path.isfile(os.path.join(directory, LOCKFILE)):
        found.append(LOCKFILE)

    locks = os.path.join(directory, DEPENDENCY_LOCKS)
    if os.path.isdir(locks):
        found += [
            "%s/%s" % (DEPENDENCY_LOCKS, name)
            for name in sorted(os.listdir(locks)) if name.endswith(".lockfile")
        ]

    return found


def locked_in(text, fallback):
    found = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        coordinate, _, configurations = stripped.partition("=")
        parts = coordinate.strip().split(":")
        if len(parts) != 3 or not all(parts):
            continue
        named = [it.strip() for it in configurations.split(",") if it.strip()]
        found.append((parts[0] + ":" + parts[1], parts[2], named or [fallback]))

    return found


def group_of(dependency):
    return dependency["path"].partition(":")[0]


def supplying(dependency, platforms):
    supplier = None
    for platform in platforms:
        if platform["version"] is None or not covers(group_of(platform), group_of(dependency)):
            continue
        if supplier is None or len(group_of(platform)) > len(group_of(supplier)):
            supplier = platform

    return supplier


def covers(group, dependent):
    return dependent == group or dependent.startswith(group + ".")


def managed(dependencies, platforms):
    for dependency in dependencies:
        if dependency["version"] is not None or dependency.get("platform"):
            continue
        supplier = supplying(dependency, platforms)
        if supplier is None:
            continue
        dependency["version"] = supplier["version"]
        dependency["managedBy"] = supplier["path"] + ":" + supplier["version"]


def add(found, index, declaration):
    existing = index.get(declaration["path"])
    if existing is None:
        index[declaration["path"]] = declaration
        found.append(declaration)

        return

    merge(existing, declaration["scopes"])


def merge(existing, scopes):
    for scope in scopes:
        if scope not in existing["scopes"]:
            existing["scopes"].append(scope)


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)

    if not collector.facts["exists"]:
        collector.facts["dependencies"] = {"direct": [], "transitive": []}
        collector.facts["lockfiles"] = []
        collector.invalid("%s is not a directory" % project_dir)

    settings = next((name for name in SETTINGS if os.path.isfile(os.path.join(project_dir, name))), None)
    manifest = manifest_in(project_dir)

    sources = [name for name in MANIFESTS + [VERSION_CATALOG] if os.path.isfile(os.path.join(project_dir, name))]

    if settings is None and not sources:
        collector.nothing("no Gradle build in %s" % project_dir)

    root = collector.above(*SETTINGS, directory=project_dir) if settings is None else None
    root_dir = os.path.join(project_dir, root) if root else None
    root_settings = beside(root, root_dir, SETTINGS)
    root_manifest = beside(root, root_dir, MANIFESTS)

    catalog_source = VERSION_CATALOG if VERSION_CATALOG in sources else beside(root, root_dir, [VERSION_CATALOG])

    read_files = sources + [it for it in [root_manifest, catalog_source] if it and it not in sources]

    collector.facts["root"] = located(root) if root else None
    collector.facts["settings"] = located(settings or root_settings) if settings or root_settings else None
    collector.facts["manifest"] = located(manifest) if manifest else None
    collector.facts["sources"] = [located(it) for it in read_files]

    catalog = sections_in(read(os.path.join(project_dir, catalog_source)) or "") if catalog_source else {}
    versions = versions_in(catalog)
    libraries = libraries_in(catalog, versions)

    collector.facts["versionCatalog"] = versions

    wrapper_dir = project_dir
    wrapper_prefix = ""
    if not os.path.isfile(os.path.join(project_dir, WRAPPER_PROPERTIES)) and root_dir:
        wrapper_dir = root_dir
        wrapper_prefix = root

    properties = read(os.path.join(wrapper_dir, WRAPPER_PROPERTIES))
    distribution = None
    checksum = None
    if properties is not None:
        for line in properties.splitlines():
            if line.startswith("distributionUrl"):
                distribution = line.partition("=")[2].strip().replace("\\:", ":")
            if line.startswith("distributionSha256Sum"):
                checksum = line.partition("=")[2].strip() or None

    version = None
    if distribution:
        named = re.search(r"gradle-([0-9][^-]*)-", distribution)
        version = named.group(1) if named else None

    collector.facts["wrapper"] = {
        "script": os.path.isfile(os.path.join(wrapper_dir, "gradlew")),
        "properties": located(wrapper_prefix, WRAPPER_PROPERTIES) if properties is not None else None,
        "distributionUrl": distribution,
        "distributionSha256Sum": checksum,
        "version": version,
    }

    projects = [{
        "path": ":",
        "directory": ".",
        "manifest": manifest,
    }]

    settings_text = read(os.path.join(project_dir, settings)) if settings else None
    for path in included_in(settings_text or ""):
        directory = slashed(os.path.join(*path.strip(":").split(":")))
        absolute = os.path.join(project_dir, directory)
        projects.append({
            "path": path,
            "directory": directory,
            "manifest": manifest_in(absolute) if os.path.isdir(absolute) else None,
        })

    collector.facts["projects"] = [{
        "path": project["path"],
        "directory": located(project["directory"]),
        "manifest": located(project["directory"], project["manifest"]) if project["manifest"] else None,
    } for project in projects]

    supplied = [
        it for it in declared_in(read(os.path.join(project_dir, root_manifest)) or "", libraries, root_manifest)
        if it.get("platform")
    ] if root_manifest else []

    direct = []
    transitive = []
    lockfiles = []
    inherited = supplied
    for project in projects:
        directory = project["directory"]
        declared = []
        resolved = []
        index = {}
        if project["manifest"]:
            source = slashed(os.path.normpath(os.path.join(directory, project["manifest"])))
            for declaration in declared_in(read(os.path.join(project_dir, source)) or "", libraries, source):
                add(declared, index, declaration)

        for lockfile in lockfiles_in(os.path.join(project_dir, directory)):
            source = slashed(os.path.normpath(os.path.join(directory, lockfile)))
            lockfiles.append(source)
            stem = os.path.basename(lockfile)[:-len(".lockfile")]
            for coordinate, locked, scopes in locked_in(read(os.path.join(project_dir, source)) or "", stem):
                existing = index.get(coordinate)
                if existing is None:
                    index[coordinate] = {
                        "path": coordinate,
                        "version": locked,
                        "scopes": list(scopes),
                        "source": source,
                    }
                    resolved.append(index[coordinate])
                    continue
                existing["version"] = locked
                merge(existing, scopes)

        platforms = [it for it in declared if it.get("platform")]
        managed(declared, platforms + inherited)
        if project["path"] == ":":
            inherited = platforms + supplied

        direct += declared
        transitive += resolved

    for dependency in direct + transitive:
        dependency["source"] = located(dependency["source"])

    collector.facts["dependencies"] = {"direct": direct, "transitive": transitive}
    collector.facts["lockfiles"] = [located(it) for it in lockfiles]
