#!/usr/bin/env python3
import os
import re

from guardrail import Collector

MANIFESTS = ["build.gradle.kts", "build.gradle"]
MAVEN_PROPERTIES = ["maven.compiler.release", "maven.compiler.source", "maven.compiler.target"]
TOOLCHAIN = re.compile(r"JavaLanguageVersion\.of\(\s*[\"']?([0-9]+)[\"']?\s*\)")
COMPATIBILITY = re.compile(
    r"\b(?:source|target)Compatibility\s*(?:=|\.set\(|\s)\s*[\"']?(?:JavaVersion\.VERSION_)?([0-9_.]+)[\"']?"
)
RELEASE = re.compile(r"\b(?:options\.)?release(?:\.set\(|\s*=\s*|\s*\.\s*set\(\s*)\s*[\"']?([0-9]+)[\"']?")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def uncommented(text):
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    return "\n".join(line.split("//", 1)[0] for line in without_blocks.splitlines())


def release_of(version):
    normalised = version.replace("_", ".").strip(".")

    if normalised.startswith("1."):
        tail = normalised[2:].split(".")[0]

        return tail or None

    return normalised.split(".")[0] or None


def declared_in(directory):
    for name in MANIFESTS:
        text = read(os.path.join(directory, name))
        if text is None:
            continue

        body = uncommented(text)

        for pattern, mechanism in ((TOOLCHAIN, "toolchain"), (RELEASE, "release"), (COMPATIBILITY, "compatibility")):
            found = pattern.search(body)
            if not found:
                continue
            version = release_of(found.group(1))
            if version is None:
                continue

            return {
                "version": version,
                "source": name,
                "mechanism": mechanism,
                "reproducible": mechanism == "toolchain",
            }

    return None


with Collector() as collector:
    project_dir = collector.input("projectDir", ".")

    def located(*parts):
        return collector.path(project_dir, *parts)

    def declared_at(*parts):
        found = declared_in(os.path.join(project_dir, *parts))

        return dict(found, source=located(*(parts + (found["source"],)))) if found else None

    collector.facts["directory"] = located()
    collector.facts["exists"] = False
    collector.facts["sources"] = []
    collector.facts["declared"] = None
    collector.facts["toolchain"] = False
    collector.facts["projects"] = []

    gradle = collector.optional("gradle", {})
    maven = collector.optional("maven", {})

    if not gradle and not maven:
        collector.nothing("no Gradle or Maven build in %s" % project_dir)

    collector.facts["exists"] = bool(gradle.get("exists") or maven.get("exists"))

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    collector.facts["sources"] = list(gradle.get("sources") or []) + list(maven.get("sources") or [])

    in_gradle = declared_at()
    if in_gradle is None and gradle.get("root"):
        in_gradle = declared_at(collector.within(gradle["root"], project_dir))
    in_maven = None
    properties = maven.get("properties") or {}

    for name in MAVEN_PROPERTIES:
        version = release_of(properties[name]) if properties.get(name) else None
        if version and maven.get("pom"):
            in_maven = {
                "version": version,
                "source": maven["pom"],
                "mechanism": "property",
                "reproducible": False,
            }
            break

    collector.facts["declared"] = in_gradle or in_maven

    projects = []
    for project in gradle.get("projects") or []:
        directory = collector.within(project["directory"], project_dir)
        declared = in_gradle if directory == "." else declared_at(directory)
        projects.append({
            "path": project["path"],
            "directory": project["directory"],
            "declared": declared,
        })

    collector.facts["projects"] = projects
    collector.facts["toolchain"] = any(
        (it["declared"] or {}).get("mechanism") == "toolchain" for it in projects
    ) or (collector.facts["declared"] or {}).get("mechanism") == "toolchain"
