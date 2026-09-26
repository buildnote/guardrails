#!/usr/bin/env python3
import fnmatch
import json
import os
import re
import shlex

from guardrail import Collector

DEFAULT_DOCKERFILES = "Dockerfile,Dockerfile.*,*.Dockerfile"

DEFAULT_REPORTS = "hadolint*.sarif,hadolint*.json,*hadolint*.sarif"

INSTRUCTIONS = (
    "ADD", "ARG", "CMD", "COPY", "ENTRYPOINT", "ENV", "EXPOSE", "FROM", "HEALTHCHECK", "LABEL",
    "MAINTAINER", "ONBUILD", "RUN", "SHELL", "STOPSIGNAL", "USER", "VOLUME", "WORKDIR",
)

HEREDOC = re.compile(r"""<<-?\s*["']?([A-Za-z_][A-Za-z0-9_]*)["']?""")

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

MAX_MESSAGE = 500

MAX_FINDINGS = 200

SARIF_LEVELS = {"error": "high", "warning": "medium", "note": "low", "none": "info"}

FILE_URI = re.compile(r"^file://[^/]*")


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def matched(path, patterns):
    name = os.path.basename(path)

    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def limited(configured):
    try:
        return int(configured)
    except ValueError:
        return MAX_FINDINGS


def unique(values):
    found = []

    for value in values:
        if value not in found:
            found.append(value)

    return found


def past_heredoc(numbered, index, line):
    delimiter = HEREDOC.search(line)

    if delimiter is None:
        return index

    while index < len(numbered):
        if numbered[index][1] == delimiter.group(1):
            return index + 1
        index += 1

    return index


def lines_in(text):
    numbered = [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if not line.strip().startswith("#")
    ]

    found = []
    index = 0

    while index < len(numbered):
        number, line = numbered[index]
        index += 1

        if not line:
            continue

        while line.endswith("\\") and index < len(numbered):
            line = line[:-1] + " " + numbered[index][1]
            index += 1

        found.append((number, line.rstrip("\\").strip()))
        index = past_heredoc(numbered, index, line)

    return found


def reference(image):
    remainder, _, digest = image.partition("@")
    registry = None
    head, _, tail = remainder.partition("/")

    if tail and ("." in head or ":" in head or head == "localhost"):
        registry, remainder = head, tail

    repository, tag = remainder, None

    if ":" in remainder.rsplit("/", 1)[-1]:
        repository, _, tag = remainder.rpartition(":")

    return {
        "registry": registry,
        "repository": repository or None,
        "tag": tag or None,
        "digest": digest or None,
    }


def stage_in(remainder):
    tokens = remainder.split()
    platform = None

    while tokens and tokens[0].startswith("--"):
        flag = tokens.pop(0)
        if flag.lower().startswith("--platform="):
            platform = flag.split("=", 1)[1]

    if not tokens:
        return None

    named = tokens[2] if len(tokens) > 2 and tokens[1].upper() == "AS" else None
    pinned = reference(tokens[0])

    return {
        "name": named,
        "image": tokens[0],
        "registry": pinned["registry"],
        "repository": pinned["repository"],
        "tag": pinned["tag"],
        "digest": pinned["digest"],
        "platform": platform,
    }


def quoted(remainder):
    try:
        return shlex.split(remainder, posix=True)
    except ValueError:
        return remainder.split()


def names_in(remainder):
    tokens = quoted(remainder)

    if tokens and "=" not in tokens[0]:
        tokens = tokens[:1]

    return [name for name in (token.split("=", 1)[0] for token in tokens) if NAME.fullmatch(name)]


def sources_in(remainder):
    stripped = remainder.strip()

    if stripped.startswith("["):
        try:
            tokens = [token for token in json.loads(stripped) if isinstance(token, str)]
        except ValueError:
            tokens = []
    else:
        tokens = [token for token in stripped.split() if not token.startswith("--")]

    return tokens[:-1] if len(tokens) > 1 else tokens


def unreadable(numbers):
    if len(numbers) == 1:
        return "line %d could not be read as an instruction" % numbers[0]

    return "lines %s could not be read as instructions" % ", ".join(str(number) for number in numbers)


def described(path, text):
    stages, ports, arguments, variables, copied, unparsed = [], [], [], [], [], []
    counts = {}
    user = None
    healthcheck = False

    for number, line in lines_in(text):
        tokens = line.split(None, 1)
        keyword = tokens[0].upper()
        remainder = tokens[1] if len(tokens) > 1 else ""

        if keyword not in INSTRUCTIONS:
            unparsed.append(number)
            continue

        counts[keyword] = counts.get(keyword, 0) + 1

        if keyword == "FROM":
            stage = stage_in(remainder)
            if stage is None:
                unparsed.append(number)
            else:
                stages.append(stage)
        elif keyword == "EXPOSE":
            ports += remainder.split()
        elif keyword == "ARG":
            arguments += names_in(remainder)
        elif keyword == "ENV":
            variables += names_in(remainder)
        elif keyword in ("COPY", "ADD"):
            copied += sources_in(remainder)
        elif keyword == "USER" and remainder.split():
            user = remainder.split()[0]
        elif keyword == "HEALTHCHECK":
            healthcheck = bool(remainder.split()) and remainder.split()[0].upper() != "NONE"

    facts = {
        "path": path,
        "stages": stages,
        "user": user,
        "exposedPorts": unique(ports),
        "healthcheck": healthcheck,
        "buildArgs": unique(arguments),
        "envKeys": unique(variables),
        "copiedPaths": unique(copied),
        "instructions": counts,
    }

    if unparsed:
        facts["unparsed"] = unreadable(unparsed)

    return facts


def parsed(text):
    if not isinstance(text, str):
        return None

    try:
        return json.loads(text)
    except ValueError:
        return None


def mapping(value):
    return value if isinstance(value, dict) else {}


def listing(value):
    return value if isinstance(value, list) else []


def text_of(value):
    return value if isinstance(value, str) else None


def integer_of(value):
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return None

    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None

    return None


def scored_severity(value):
    if isinstance(value, bool):
        return None

    try:
        score = float(value)
    except (TypeError, ValueError):
        return None

    if score >= 9.0:
        return "critical"

    if score >= 7.0:
        return "high"

    if score >= 4.0:
        return "medium"

    if score > 0:
        return "low"

    return "info"


def sarif_rule(result, rules, by_id, identifier):
    index = integer_of(result.get("ruleIndex"))

    if index is None:
        index = integer_of(mapping(result.get("rule")).get("index"))

    if index is not None and 0 <= index < len(rules):
        return mapping(rules[index])

    return mapping(by_id.get(identifier))


def sarif_severity(result, rule):
    for properties in [mapping(result.get("properties")), mapping(rule.get("properties"))]:
        scored = scored_severity(properties.get("security-severity"))

        if scored:
            return scored

    level = text_of(result.get("level")) or text_of(mapping(rule.get("defaultConfiguration")).get("level")) or ""

    return SARIF_LEVELS.get(level.lower(), "unknown")


def sarif_path(uri):
    if not isinstance(uri, str):
        return None

    stripped = FILE_URI.sub("", uri)

    if stripped.startswith("./"):
        stripped = stripped[2:]

    return stripped or None


def sarif_finding(result, rules, by_id):
    identifier = text_of(result.get("ruleId")) or text_of(mapping(result.get("rule")).get("id"))
    rule = sarif_rule(result, rules, by_id, identifier)
    locations = listing(result.get("locations"))
    physical = mapping(mapping(locations[0]).get("physicalLocation")) if locations else {}
    message = text_of(mapping(result.get("message")).get("text")) \
        or text_of(mapping(rule.get("shortDescription")).get("text")) \
        or ""

    return {
        "id": identifier or text_of(rule.get("id")) or "",
        "severity": sarif_severity(result, rule),
        "message": message[:MAX_MESSAGE],
        "path": sarif_path(mapping(physical.get("artifactLocation")).get("uri")),
        "line": integer_of(mapping(physical.get("region")).get("startLine")),
    }


def sarif(text):
    document = parsed(text)

    if not isinstance(document, dict) or not isinstance(document.get("runs"), list):
        return None

    tool = None
    findings = []

    for run in document["runs"]:
        driver = mapping(mapping(mapping(run).get("tool")).get("driver"))
        rules = listing(driver.get("rules"))
        by_id = dict((mapping(rule).get("id"), rule) for rule in rules if text_of(mapping(rule).get("id")))
        name = text_of(driver.get("name")) or ""

        if tool is None and name:
            tool = {
                "name": name,
                "version": text_of(driver.get("version")) or text_of(driver.get("semanticVersion")),
            }

        for result in listing(mapping(run).get("results")):
            findings.append(sarif_finding(mapping(result), rules, by_id))

    return {"tool": tool, "findings": findings}


with Collector() as collector:
    narrowed = globs(collector.input("dockerfiles", DEFAULT_DOCKERFILES))
    dockerfiles = [
        (path, text)
        for path, _, text in collector.reports(*globs(DEFAULT_DOCKERFILES))
        if matched(path, narrowed)
    ]

    collector.facts["dockerfiles"] = [described(collector.path(path), text) for path, text in dockerfiles]

    if not dockerfiles:
        collector.empty("no Dockerfile matched %s" % ", ".join(narrowed))

    patterns = globs(collector.input("reports", DEFAULT_REPORTS))
    limit = limited(collector.input("maxFindings", str(MAX_FINDINGS)))
    read = []
    findings = []

    for path, modified, text in collector.reports(*patterns):
        normalized = sarif(text)

        if normalized is None:
            collector.log("%s is no SARIF document and was not read" % path)
            continue

        producer = normalized.get("tool") or {}
        read.append({
            "path": collector.path(path),
            "modified": modified,
            "format": "sarif",
            "producer": {"name": producer.get("name"), "version": producer.get("version")},
        })
        findings += normalized["findings"]

    if not read:
        collector.empty("no hadolint report matched %s" % ", ".join(patterns))

    collector.sourced("report", read)
    collector.facts["lint"] = {
        "findings": findings[:limit],
        "total": len(findings),
        "dropped": max(0, len(findings) - limit),
    }
