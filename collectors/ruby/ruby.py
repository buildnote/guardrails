#!/usr/bin/env python3
import glob
import os
import re

from guardrail import Collector

GEMFILE = "Gemfile"
LOCKFILE = "Gemfile.lock"
RUBY_VERSION = ".ruby-version"
DEFAULT_SCOPE = "default"
GEM = re.compile(r"^\s*gem\s+['\"]([^'\"]+)['\"](.*)$")
GROUP = re.compile(r"^\s*group\s+(.+?)\s+do\s*$")
BLOCK = re.compile(r"\bdo\s*$|^\s*(if|unless|case|begin|def)\b")
END = re.compile(r"^\s*end\s*$")
RUBY = re.compile(r"^\s*ruby\s+['\"]([^'\"]+)['\"]", re.M)
SOURCE = re.compile(r"^\s*source\s+['\"]([^'\"]+)['\"]", re.M)
NAME = re.compile(r"\.name\s*=\s*['\"]([^'\"]+)['\"]")
REQUIRED_RUBY = re.compile(r"required_ruby_version\s*=\s*[^'\"\n]*['\"]([^'\"]+)['\"]")
SYMBOL = re.compile(r"[:'\"]([A-Za-z0-9_]+)['\"]?")
REQUIREMENT = re.compile(r"^\s*,\s*['\"]([^'\"]+)['\"]")
BUNDLED = re.compile(r"^BUNDLED WITH\s*\n\s*([0-9][^\s]*)", re.M)
UNPINNED = ("~", ">", "<", "*", "!")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def pinned(requirement, options):
    if "git:" in options or "github:" in options or "path:" in options:
        return False
    if not requirement:
        return False

    return not any(marker in requirement for marker in UNPINNED)


def origin_of(options):
    if "git:" in options or "github:" in options:
        return "git"
    if "path:" in options:
        return "path"

    return "registry"


def groups_in(text):
    found = [it.strip() for it in SYMBOL.findall(text)]

    return found or [DEFAULT_SCOPE]


def gems_in(text, source):
    found = []
    groups = []
    depth = []

    for line in text.splitlines():
        body = line.split("#", 1)[0]

        if END.match(body):
            if depth:
                closed = depth.pop()
                if closed is not None:
                    groups.pop()
            continue

        opened = GROUP.match(body)
        if opened:
            groups.append(groups_in(opened.group(1)))
            depth.append(True)
            continue

        declared = GEM.match(body)
        if declared:
            options = declared.group(2)
            requirement = REQUIREMENT.match(options)
            found.append({
                "name": declared.group(1),
                "version": requirement.group(1) if requirement else None,
                "scopes": list(groups[-1]) if groups else [DEFAULT_SCOPE],
                "source": source,
                "pinned": pinned(requirement.group(1) if requirement else None, options),
                "origin": origin_of(options),
            })
            continue

        if BLOCK.search(body):
            depth.append(None)

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
    collector.facts["declared"] = None
    collector.facts["bundler"] = None
    collector.facts["sources_declared"] = []
    collector.facts["projects"] = []
    collector.facts["dependencies"] = {"direct": [], "transitive": []}
    collector.facts["lockfiles"] = []
    collector.facts["unparsed"] = []

    if not collector.facts["exists"]:
        collector.invalid("%s is not a directory" % project_dir)

    gemspecs = sorted(
        os.path.relpath(it, project_dir).replace(os.sep, "/")
        for it in glob.glob(os.path.join(project_dir, "*.gemspec"))
    )
    gemfile = read(os.path.join(project_dir, GEMFILE))

    if gemfile is None and not gemspecs:
        collector.nothing("no Bundler project in %s" % project_dir)

    sources = []
    dependencies = []

    if gemfile is not None:
        sources.append(GEMFILE)
        collector.facts["scanned"].append(GEMFILE)
        collector.facts["sources_declared"] = SOURCE.findall(gemfile)
        dependencies += gems_in(gemfile, GEMFILE)
        found = RUBY.search(gemfile)
        if found:
            collector.facts["declared"] = {
                "version": found.group(1),
                "source": GEMFILE,
                "pinned": not any(marker in found.group(1) for marker in UNPINNED),
            }

    name = None
    for gemspec in gemspecs:
        text = read(os.path.join(project_dir, gemspec))
        if text is None:
            collector.facts["unparsed"].append({"path": gemspec, "reason": "the gemspec could not be read"})
            continue
        sources.append(gemspec)
        collector.facts["scanned"].append(gemspec)
        declared = NAME.search(text)
        if declared and name is None:
            name = declared.group(1)

        required = REQUIRED_RUBY.search(text)
        if required and collector.facts["declared"] is None:
            collector.facts["declared"] = {
                "version": required.group(1).strip(),
                "source": gemspec,
                "pinned": not any(marker in required.group(1) for marker in UNPINNED),
            }

    text = read(os.path.join(project_dir, RUBY_VERSION))
    if text and text.strip():
        collector.facts["declared"] = {
            "version": text.strip(),
            "source": RUBY_VERSION,
            "pinned": not any(marker in text.strip() for marker in UNPINNED),
        }

    lock = read(os.path.join(project_dir, LOCKFILE))
    if lock is not None:
        collector.facts["lockfiles"] = [located(LOCKFILE)]
        bundled = BUNDLED.search(lock)
        collector.facts["bundler"] = bundled.group(1) if bundled else None

    manifest = GEMFILE if gemfile is not None else (gemspecs[0] if gemspecs else None)

    for dependency in dependencies:
        dependency["source"] = located(dependency["source"])

    for entry in collector.facts["unparsed"]:
        entry["path"] = located(entry["path"])

    if collector.facts["declared"]:
        collector.facts["declared"]["source"] = located(collector.facts["declared"]["source"])

    collector.facts["scanned"] = [located(it) for it in collector.facts["scanned"]]
    collector.facts["manifest"] = located(manifest) if manifest else None
    collector.facts["sources"] = [located(it) for it in sources]
    collector.facts["projects"] = [{
        "path": located("."),
        "manifest": located(gemspecs[0] if gemspecs else GEMFILE),
        "name": name,
    }]
    collector.facts["dependencies"] = {"direct": dependencies, "transitive": []}
