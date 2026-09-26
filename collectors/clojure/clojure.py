#!/usr/bin/env python3
import os
import re

from guardrail import Collector

DEPS = "deps.edn"
PROJECT = "project.clj"
DEFAULT_SCOPE = "default"
CLOJURE = "org.clojure/clojure"
MOVING = ("RELEASE", "LATEST", "SNAPSHOT")
TOKEN = re.compile(r"[^\s,\[\]{}()\"]+")
DEFPROJECT = re.compile(r"\(defproject\s+([^\s]+)\s+\"([^\"]+)\"")
LEIN_DEPENDENCY = re.compile(r"\[\s*([^\s\[\]]+)\s+\"([^\"]+)\"")


class Unreadable(Exception):
    pass


class Keyword(str):
    pass


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def uncommented(text):
    return "\n".join(line.split(";", 1)[0] for line in text.splitlines())


class Edn(object):
    def __init__(self, text):
        self.text = text
        self.at = 0

    def spaces(self):
        while self.at < len(self.text) and self.text[self.at] in " \t\r\n,":
            self.at += 1

    def peek(self):
        return "" if self.at >= len(self.text) else self.text[self.at]

    def value(self):
        self.spaces()
        character = self.peek()

        if character == "":
            raise Unreadable("the document ends early")
        if character == "{":
            return self.collection("}", mapping=True)
        if character == "[":
            return self.collection("]")
        if character == "(":
            return self.collection(")")
        if character == "#":
            self.at += 1
            if self.peek() == "{":
                return self.collection("}")
            if self.peek() == "_":
                self.at += 1
                self.value()
                return self.value()
            self.token()
            return self.value()
        if character == "\"":
            return self.string()

        return self.atom()

    def collection(self, closing, mapping=False):
        self.at += 1
        found = []

        while True:
            self.spaces()
            if self.peek() == "":
                raise Unreadable("a collection is not closed")
            if self.peek() == closing:
                self.at += 1
                break
            found.append(self.value())

        if not mapping:
            return found
        if len(found) % 2:
            raise Unreadable("a map has a key with no value")

        return dict((self.keyed(found[it]), found[it + 1]) for it in range(0, len(found), 2))

    def keyed(self, key):
        return key if isinstance(key, str) else str(key)

    def string(self):
        self.at += 1
        built = []

        while True:
            if self.at >= len(self.text):
                raise Unreadable("a string is not closed")
            character = self.text[self.at]
            self.at += 1
            if character == "\"":
                return "".join(built)
            if character == "\\":
                if self.at >= len(self.text):
                    raise Unreadable("a string is not closed")
                built.append({"n": "\n", "t": "\t", "r": "\r"}.get(self.text[self.at], self.text[self.at]))
                self.at += 1
                continue
            built.append(character)

    def token(self):
        found = TOKEN.match(self.text, self.at)
        if not found:
            raise Unreadable("a value could not be read")
        self.at = found.end()

        return found.group(0)

    def atom(self):
        text = self.token()

        if text == "nil":
            return None
        if text in ("true", "false"):
            return text == "true"
        if text.startswith(":"):
            return Keyword(text[1:])

        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            return text


def parsed(text):
    reader = Edn(uncommented(text))
    document = reader.value()
    reader.spaces()

    if reader.peek() != "":
        raise Unreadable("more than one form")

    return document


def pinned(version, origin, coordinate):
    if origin == "git":
        return bool(coordinate.get("git/sha"))
    if origin == "local":
        return False

    return bool(version) and not any(marker in version for marker in MOVING)


def coordinates_in(declared, scope, source):
    found = []

    for name, coordinate in (declared or {}).items():
        if not isinstance(coordinate, dict):
            coordinate = {}
        origin = "maven"
        if "git/url" in coordinate or "git/tag" in coordinate or "git/sha" in coordinate:
            origin = "git"
        elif "local/root" in coordinate:
            origin = "local"
        version = coordinate.get("mvn/version") or coordinate.get("git/tag")
        found.append({
            "name": name,
            "version": version if isinstance(version, str) else None,
            "scopes": [scope],
            "source": source,
            "pinned": pinned(version if isinstance(version, str) else None, origin, coordinate),
            "origin": origin,
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
    collector.facts["tool"] = None
    collector.facts["declared"] = None
    collector.facts["paths"] = []
    collector.facts["aliases"] = []
    collector.facts["repositories"] = []
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    deps = read(os.path.join(project_dir, DEPS))
    lein = read(os.path.join(project_dir, PROJECT))

    if deps is None and lein is None:
        collector.nothing("no Clojure build in %s" % project_dir)

    collector.facts["tool"] = "both" if deps is not None and lein is not None else (
        "clojure-cli" if deps is not None else "leiningen"
    )
    collector.facts["manifest"] = located(DEPS if deps is not None else PROJECT)

    sources = []
    dependencies = []
    projects = []

    if deps is not None:
        try:
            document = parsed(deps)
        except Unreadable as rejected:
            collector.facts["unparsed"].append({"path": DEPS, "reason": str(rejected)})
            document = None
        except Exception:
            collector.facts["unparsed"].append({"path": DEPS, "reason": "the manifest could not be read"})
            document = None

        if isinstance(document, dict):
            sources.append(DEPS)
            projects.append({"path": ".", "manifest": DEPS, "name": None})
            collector.facts["paths"] = [it for it in (document.get("paths") or []) if isinstance(it, str)]
            dependencies += coordinates_in(document.get("deps"), DEFAULT_SCOPE, DEPS)

            aliases = document.get("aliases") if isinstance(document.get("aliases"), dict) else {}
            collector.facts["aliases"] = sorted(aliases)
            for alias in sorted(aliases):
                declared = aliases[alias] if isinstance(aliases[alias], dict) else {}
                dependencies += coordinates_in(declared.get("extra-deps"), alias, DEPS)
                dependencies += coordinates_in(declared.get("replace-deps"), alias, DEPS)

            repositories = document.get("mvn/repos") if isinstance(document.get("mvn/repos"), dict) else {}
            for name in sorted(repositories):
                entry = repositories[name] if isinstance(repositories[name], dict) else {}
                url = entry.get("url")
                collector.facts["repositories"].append({"name": name, "url": url if isinstance(url, str) else None})

    if lein is not None:
        body = uncommented(lein)
        sources.append(PROJECT)
        collector.facts["scanned"].append(PROJECT)
        named = DEFPROJECT.search(body)
        projects.append({"path": ".", "manifest": PROJECT, "name": named.group(1) if named else None})

        for section in re.finditer(r":dependencies\s*\[(.*?)\]\s*\]", body, re.S):
            for declared in LEIN_DEPENDENCY.finditer(section.group(1) + "]"):
                version = declared.group(2)
                dependencies.append({
                    "name": declared.group(1),
                    "version": version,
                    "scopes": [DEFAULT_SCOPE],
                    "source": PROJECT,
                    "pinned": not any(marker in version for marker in MOVING),
                    "origin": "maven",
                })

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    for dependency in dependencies:
        if dependency["name"] == CLOJURE and dependency["version"]:
            collector.facts["declared"] = {
                "version": dependency["version"],
                "source": dependency["source"],
                "pinned": dependency["pinned"],
            }
            break

    collector.facts["paths"] = [located(it) for it in collector.facts["paths"]]
    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["scanned"] = [located(it) for it in collector.facts["scanned"]]
    collector.facts["projects"] = [{
        "path": located(it["path"]),
        "manifest": located(it["manifest"]),
        "name": it["name"],
    } for it in projects]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
