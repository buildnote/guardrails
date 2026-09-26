#!/usr/bin/env python3
import os
import re
import xml.etree.ElementTree as ElementTree

from guardrail import Collector, slashed

POM = "pom.xml"
DEFAULT_SCOPE = "compile"
IMPORT_SCOPE = "import"
PROPERTY = re.compile(r"\$\{([^}]+)\}")


def tag_of(element):
    return element.tag.split("}")[-1]


def child(element, name):
    for candidate in element:
        if tag_of(candidate) == name:
            return candidate

    return None


def text_of(element, name):
    found = child(element, name)

    return found.text.strip() if found is not None and found.text else None


def parse(path):
    try:
        return ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None


def coordinates_of(root):
    parent = child(root, "parent")

    return {
        "groupId": text_of(root, "groupId") or (text_of(parent, "groupId") if parent is not None else None),
        "artifactId": text_of(root, "artifactId"),
        "version": text_of(root, "version") or (text_of(parent, "version") if parent is not None else None),
        "packaging": text_of(root, "packaging") or "jar",
    }


def properties_of(root):
    declared = child(root, "properties")
    if declared is None:
        return {}

    return dict((tag_of(entry), (entry.text or "").strip()) for entry in declared)


def modules_of(root):
    declared = child(root, "modules")
    if declared is None:
        return []

    return [(entry.text or "").strip() for entry in declared if (entry.text or "").strip()]


def resolved(value, properties):
    if value is None:
        return None

    for _ in range(5):
        replaced = PROPERTY.sub(lambda found: properties.get(found.group(1), found.group(0)), value)
        if replaced == value:
            break
        value = replaced

    return None if PROPERTY.search(value) else value


def resolvable(properties, coordinates):
    named = dict(properties)
    for prefix in ("project", "pom"):
        named.setdefault(prefix + ".groupId", coordinates["groupId"] or "")
        named.setdefault(prefix + ".artifactId", coordinates["artifactId"] or "")
        named.setdefault(prefix + ".version", coordinates["version"] or "")

    return named


def entries_of(root, name):
    holder = child(root, name) if name != "dependencies" else root
    declared = child(holder, "dependencies") if holder is not None else None
    if declared is None:
        return []

    return [entry for entry in declared if tag_of(entry) == "dependency"]


def path_of(entry, properties):
    group = resolved(text_of(entry, "groupId"), properties)
    name = resolved(text_of(entry, "artifactId"), properties)

    return group + ":" + name if group and name else None


def managed_of(root, properties):
    managed = {}
    for entry in entries_of(root, "dependencyManagement"):
        if text_of(entry, "scope") == IMPORT_SCOPE:
            continue
        managed[path_of(entry, properties)] = text_of(entry, "version")

    return managed


def imports_of(root, source, properties, profile=None):
    found = []
    for entry in entries_of(root, "dependencyManagement"):
        if text_of(entry, "scope") != IMPORT_SCOPE:
            continue
        path = path_of(entry, properties)
        if path is None:
            continue
        imported = {
            "path": path,
            "version": resolved(text_of(entry, "version"), properties),
            "scopes": [IMPORT_SCOPE],
            "source": source,
            "platform": True,
        }
        if profile:
            imported["profile"] = profile
        found.append(imported)

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


def profiles_of(root):
    declared = child(root, "profiles")
    if declared is None:
        return []

    return [entry for entry in declared if tag_of(entry) == "profile"]


def dependencies_of(root, source, properties, versions, profile=None):
    found = []
    for entry in entries_of(root, "dependencies"):
        path = path_of(entry, properties)
        if path is None:
            continue
        declared = {
            "path": path,
            "version": resolved(text_of(entry, "version") or versions.get(path), properties),
            "scopes": [text_of(entry, "scope") or DEFAULT_SCOPE],
            "source": source,
        }
        if profile:
            declared["profile"] = profile
        found.append(declared)

    return found


def declared_in(root, source, properties, versions, inherited):
    found = imports_of(root, source, properties)
    found += dependencies_of(root, source, properties, versions)
    for profile in profiles_of(root):
        named = text_of(profile, "id")
        scoped = dict(properties, **properties_of(profile))
        found += imports_of(profile, source, scoped, named)
        found += dependencies_of(profile, source, scoped, dict(versions, **managed_of(profile, scoped)), named)

    managed(found, [it for it in found if it.get("platform")] + inherited)

    return found


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    collector.facts["directory"] = located()
    collector.facts["exists"] = os.path.isdir(project_dir)
    collector.facts["pom"] = None
    collector.facts["sources"] = []
    collector.facts["modules"] = []
    collector.facts["properties"] = {}
    collector.facts["coordinates"] = None
    collector.facts["dependencies"] = {"direct": [], "transitive": []}

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    path = os.path.join(project_dir, POM)
    if not os.path.isfile(path):
        collector.nothing("no Maven build in %s" % project_dir)

    collector.facts["pom"] = located(POM)
    collector.facts["sources"] = [located(POM)]
    collector.facts["root"] = None

    root = parse(path)
    if root is None:
        collector.facts["malformed"] = True
        collector.invalid("%s could not be parsed" % path)

    parent = child(root, "parent")
    detached = parent is not None and child(parent, "relativePath") is not None \
        and text_of(parent, "relativePath") is None
    above = collector.above(POM, directory=project_dir) if parent is not None and not detached else None
    inheritable = parse(os.path.join(project_dir, above, POM)) if above else None

    if inheritable is None:
        above = None

    parent_source = slashed(os.path.normpath(os.path.join(above, POM))) if above else None
    parent_properties = properties_of(inheritable) if above else {}
    parent_resolvable = resolvable(parent_properties, coordinates_of(inheritable)) if above else {}
    parent_versions = managed_of(inheritable, parent_resolvable) if above else {}
    parent_platforms = imports_of(inheritable, parent_source, parent_resolvable) if above else []

    collector.facts["malformed"] = False
    collector.facts["root"] = located(above) if above else None
    collector.facts["sources"] = [located(it) for it in [POM] + ([parent_source] if parent_source else [])]
    collector.facts["coordinates"] = coordinates_of(root)
    collector.facts["properties"] = dict(parent_properties, **properties_of(root))

    inherited = resolvable(collector.facts["properties"], collector.facts["coordinates"])
    versions = dict(parent_versions, **managed_of(root, inherited))
    platforms = parent_platforms + imports_of(root, POM, inherited)
    dependencies = declared_in(root, POM, inherited, versions, parent_platforms)

    modules = []
    for module in modules_of(root):
        module_pom = slashed(os.path.join(module, POM))
        modules.append({
            "path": module,
            "pom": module_pom if os.path.isfile(os.path.join(project_dir, module_pom)) else None,
            "coordinates": None,
        })
        parsed = parse(os.path.join(project_dir, module_pom))
        if parsed is None:
            continue

        modules[-1]["coordinates"] = coordinates_of(parsed)
        properties = dict(inherited, **properties_of(parsed))
        properties = resolvable(properties, modules[-1]["coordinates"])
        dependencies += declared_in(
            parsed,
            module_pom,
            properties,
            dict(versions, **managed_of(parsed, properties)),
            platforms,
        )

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    collector.facts["modules"] = [{
        "path": located(module["path"]),
        "pom": located(module["pom"]) if module["pom"] else None,
        "coordinates": module["coordinates"],
    } for module in modules]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
