#!/usr/bin/env python3
import os
import re

from guardrail import Collector

MANIFESTS = ["build.gradle.kts", "build.gradle"]
VERSION_CATALOG = "gradle/libs.versions.toml"
CATALOG_VERSION = "kotlin"
MAVEN_PROPERTY = "kotlin.version"

PATTERNS = {
    "build.gradle.kts": [
        r"""kotlin\(["'][^"']+["']\)\s*version\s*["']([^"']+)["']""",
        r"""id\(["']org\.jetbrains\.kotlin[^"']*["']\)\s*version\s*["']([^"']+)["']""",
    ],
    "build.gradle": [
        r"""id\s*["']org\.jetbrains\.kotlin[^"']*["']\s*version\s*["']([^"']+)["']""",
    ],
}


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def declared_in(directory):
    for name in MANIFESTS:
        text = read(os.path.join(directory, name))
        if text is None:
            continue
        for pattern in PATTERNS[name]:
            found = re.search(pattern, text)
            if found:
                return {"version": found.group(1), "source": name}

    return None


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    def declared_at(*parts):
        found = declared_in(os.path.join(project_dir, *parts))

        return {"version": found["version"], "source": located(*(parts + (found["source"],)))} if found else None

    collector.facts["directory"] = located()
    collector.facts["exists"] = False
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["projects"] = []

    gradle = collector.optional("gradle", {})
    maven = collector.optional("maven", {})

    if not gradle and not maven:
        collector.nothing("no Gradle or Maven build in %s" % project_dir)

    collector.facts["exists"] = bool(gradle.get("exists") or maven.get("exists"))

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    collector.facts["sources"] = list(gradle.get("sources") or []) + list(maven.get("sources") or [])

    catalog = (gradle.get("versionCatalog") or {}).get(CATALOG_VERSION)
    pinned = (maven.get("properties") or {}).get(MAVEN_PROPERTY)
    root = gradle.get("root")

    in_gradle = declared_at()
    if in_gradle is None and root:
        in_gradle = declared_at(collector.within(root, project_dir))
    if in_gradle is None and catalog:
        in_gradle = {
            "version": catalog,
            "source": next(
                (it for it in gradle.get("sources") or [] if it.endswith(VERSION_CATALOG)),
                located(VERSION_CATALOG),
            ),
        }

    in_maven = {"version": pinned, "source": maven["pom"]} if pinned and maven.get("pom") else None

    collector.facts["declared"] = in_gradle or in_maven

    projects = []
    for project in gradle.get("projects") or []:
        directory = collector.within(project["directory"], project_dir)
        projects.append({
            "path": project["path"],
            "directory": project["directory"],
            "declared": in_gradle if directory == "." else declared_at(directory),
        })

    collector.facts["projects"] = projects
