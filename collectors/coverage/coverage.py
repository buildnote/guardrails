#!/usr/bin/env python3
import json
import re
import xml.etree.ElementTree as ElementTree

from guardrail import Collector

FORMATS = ("jacoco", "cobertura", "istanbul", "lcov")

ASKED = ("true", "1", "yes", "on")

CONDITIONS = re.compile(r"\((\d+)\s*/\s*(\d+)\)")

XML_FORMATS = {
    "report": "jacoco",
    "coverage": "cobertura",
}


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def percentage(covered, missed):
    total = covered + missed

    return round(covered * 100.0 / total, 2) if total > 0 else 0.0


def merge(files, reported):
    for path, entry in reported.items():
        found = files.setdefault(path, {"covered": set(), "missed": set()})
        found["covered"].update(entry["covered"])
        found["missed"].update(entry["missed"])


def summarised(entry, detailed):
    covered = sorted(entry["covered"])
    missed = sorted(entry["missed"] - entry["covered"])
    summary = {
        "covered": len(covered),
        "missed": len(missed),
        "percent": percentage(len(covered), len(missed)),
    }

    if detailed:
        summary["coveredLines"] = covered
        summary["missedLines"] = missed

    return summary


def unattributed(reported, kind, total):
    return total - sum(len(entry[kind]) for entry in reported.values())


def root_of(text):
    if not isinstance(text, str):
        return None
    try:
        return ElementTree.fromstring(text.lstrip("\ufeff \t\r\n"))
    except Exception:
        return None


def tag(element):
    name = element.tag
    if not isinstance(name, str):
        return ""
    return name.rsplit("}", 1)[1] if "}" in name else name


def children_of(element, name):
    return [child for child in list(element) if tag(child) == name]


def descendants_of(element, name):
    return [found for found in element.iter() if tag(found) == name]


def whole(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def amount(value):
    number = whole(value)
    return 0 if number is None else number


def mark(files, path, line, covered):
    entry = files.setdefault(path, {"covered": set(), "missed": set()})
    entry["covered" if covered else "missed"].add(line)


def resolve(files):
    return dict(
        (path, {"covered": sorted(entry["covered"]), "missed": sorted(entry["missed"] - entry["covered"])})
        for path, entry in files.items()
    )


def measured(files, extra, branches):
    resolved = resolve(files)
    covered = sum(len(entry["covered"]) for entry in resolved.values()) + extra["covered"]
    missed = sum(len(entry["missed"]) for entry in resolved.values()) + extra["missed"]

    return {
        "lines": {"covered": covered, "missed": missed, "percent": percentage(covered, missed)},
        "branches": {
            "covered": branches["covered"],
            "missed": branches["missed"],
            "percent": percentage(branches["covered"], branches["missed"]),
        } if branches["seen"] else None,
        "files": resolved,
    }


def tally():
    return {"covered": 0, "missed": 0, "seen": False}


def add(counts, covered, missed):
    counts["covered"] += covered
    counts["missed"] += missed
    counts["seen"] = True


def counter_of(element, kind):
    for counter in children_of(element, "counter"):
        if counter.get("type") == kind:
            return amount(counter.get("covered")), amount(counter.get("missed"))

    return None


def jacoco(text):
    try:
        root = root_of(text)
        if root is None or tag(root) != "report":
            return None

        files = {}
        extra = {"covered": 0, "missed": 0}
        branches = tally()

        for package in descendants_of(root, "package"):
            prefix = (package.get("name") or "").strip("/")
            for source in children_of(package, "sourcefile"):
                path = "/".join([part for part in (prefix, source.get("name") or "") if part])
                for line in children_of(source, "line"):
                    number = whole(line.get("nr"))
                    if number is None:
                        continue
                    mark(files, path, number, amount(line.get("ci")) > 0)
                    if line.get("cb") is not None or line.get("mb") is not None:
                        add(branches, amount(line.get("cb")), amount(line.get("mb")))
                if not children_of(source, "line"):
                    jacoco_counters(source, extra, branches)

        if not files and not extra["covered"] and not extra["missed"]:
            for element in descendants_of(root, "class"):
                jacoco_counters(element, extra, branches)

        return measured(files, extra, branches)
    except Exception:
        return None


def jacoco_counters(element, extra, branches):
    lines = counter_of(element, "LINE")
    if lines is not None:
        extra["covered"] += lines[0]
        extra["missed"] += lines[1]

    branch = counter_of(element, "BRANCH")
    if branch is not None:
        add(branches, branch[0], branch[1])


def lcov(text):
    try:
        if not isinstance(text, str):
            return None

        files = {}
        extra = {"covered": 0, "missed": 0}
        branches = tally()
        path = None
        seen = False
        structured = False
        counted = False
        branched = False
        totals = {}

        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("SF:"):
                path = line[3:].strip()
                seen = True
                counted = False
                branched = False
                totals = {}
            elif path is None:
                continue
            elif line.startswith("DA:"):
                parts = line[3:].split(",")
                number = whole(parts[0]) if parts else None
                if number is not None:
                    mark(files, path, number, amount(parts[1] if len(parts) > 1 else 0) > 0)
                    counted = True
                    structured = True
            elif line.startswith("BRDA:"):
                parts = line[5:].split(",")
                if len(parts) >= 4:
                    taken = parts[3].strip() not in ("-", "0", "")
                    add(branches, 1 if taken else 0, 0 if taken else 1)
                    branched = True
            elif line[:3] in ("LF:", "LH:") or line[:4] in ("BRF:", "BRH:"):
                key, _, value = line.partition(":")
                totals[key] = amount(value)
                structured = True
            elif line == "end_of_record":
                if not counted and ("LF" in totals or "LH" in totals):
                    hit = totals.get("LH", 0)
                    extra["covered"] += hit
                    extra["missed"] += max(totals.get("LF", 0) - hit, 0)
                if not branched and ("BRF" in totals or "BRH" in totals):
                    hit = totals.get("BRH", 0)
                    add(branches, hit, max(totals.get("BRF", 0) - hit, 0))
                structured = True
                path = None

        if not seen or not structured:
            return None

        return measured(files, extra, branches)
    except Exception:
        return None


def cobertura(text):
    try:
        root = root_of(text)
        if root is None or tag(root) != "coverage":
            return None

        files = {}
        branches = tally()

        for element in descendants_of(root, "class"):
            path = element.get("filename")
            if not path:
                continue
            for lines in children_of(element, "lines"):
                for line in children_of(lines, "line"):
                    number = whole(line.get("number"))
                    if number is None:
                        continue
                    mark(files, path, number, amount(line.get("hits")) > 0)
                    cobertura_conditions(line, branches)

        if not branches["seen"]:
            valid = whole(root.get("branches-valid"))
            hit = whole(root.get("branches-covered"))
            if valid is not None and hit is not None:
                add(branches, hit, max(valid - hit, 0))

        return measured(files, {"covered": 0, "missed": 0}, branches)
    except Exception:
        return None


def cobertura_conditions(line, branches):
    if (line.get("branch") or "").lower() != "true":
        return

    found = CONDITIONS.search(line.get("condition-coverage") or "")
    if found is None:
        return

    hit = int(found.group(1))
    total = int(found.group(2))
    add(branches, hit, max(total - hit, 0))


def istanbul(text):
    try:
        if not isinstance(text, str):
            return None
        document = json.loads(text)
        if not isinstance(document, dict) or not document:
            return None

        files = {}
        branches = tally()
        recognised = False

        for path, entry in document.items():
            if not isinstance(entry, dict):
                return None
            statements = entry.get("statementMap")
            hits = entry.get("s")
            if not isinstance(statements, dict) or not isinstance(hits, dict):
                return None

            recognised = True
            covered = set()
            missed = set()
            for identifier, location in statements.items():
                number = istanbul_line(location)
                if number is None:
                    continue
                if amount(hits.get(identifier)) > 0:
                    covered.add(number)
                else:
                    missed.add(number)

            for number in covered:
                mark(files, path, number, True)
            for number in missed:
                mark(files, path, number, False)

            taken = entry.get("b")
            if isinstance(taken, dict) and isinstance(entry.get("branchMap"), dict):
                for counts in taken.values():
                    if not isinstance(counts, list):
                        continue
                    add(
                        branches,
                        len([count for count in counts if amount(count) > 0]),
                        len([count for count in counts if amount(count) <= 0]),
                    )

        if not recognised:
            return None

        return measured(files, {"covered": 0, "missed": 0}, branches)
    except Exception:
        return None


def istanbul_line(location):
    if not isinstance(location, dict):
        return None
    start = location.get("start")
    if not isinstance(start, dict):
        return None

    return whole(start.get("line"))


def coverage(text):
    for parser in (jacoco, cobertura, istanbul, lcov):
        parsed = parser(text)
        if parsed is not None:
            return parsed

    return None


def detect(text):
    try:
        root = root_of(text)
        if root is not None:
            return XML_FORMATS.get(tag(root))
        if istanbul(text) is not None:
            return "istanbul"
        if lcov(text) is not None:
            return "lcov"
        return None
    except Exception:
        return None


with Collector() as collector:
    patterns = globs(collector.input("reports", "jacoco*.xml,jacocoTestReport.xml,cobertura*.xml,coverage*.xml,lcov.info,coverage-final.json"))
    limit = int(collector.input("maxFiles", "500") or "500")
    detailed = collector.input("lineDetail", "false").strip().lower() in ASKED

    read = []
    files = {}
    extra = {"covered": 0, "missed": 0}
    branches = tally()

    for path, modified, text in collector.reports(*patterns):
        format = detect(text)

        if format not in FORMATS:
            continue

        parsed = coverage(text)

        if parsed is None:
            collector.log("%s looked like %s and could not be read" % (path, format))
            continue

        read.append({"path": collector.path(path), "modified": modified, "format": format})
        merge(files, parsed["files"])

        extra["covered"] += unattributed(parsed["files"], "covered", parsed["lines"]["covered"])
        extra["missed"] += unattributed(parsed["files"], "missed", parsed["lines"]["missed"])

        if parsed["branches"] is not None:
            add(branches, parsed["branches"]["covered"], parsed["branches"]["missed"])

    if not read:
        collector.empty("no coverage report matched %s" % ", ".join(patterns))

    summaries = dict((path, summarised(entry, detailed)) for path, entry in files.items())
    ranked = sorted(summaries.items(), key=lambda entry: (-entry[1]["missed"], entry[0]))

    covered = sum(summary["covered"] for summary in summaries.values()) + extra["covered"]
    missed = sum(summary["missed"] for summary in summaries.values()) + extra["missed"]

    collector.sourced("report", read)
    collector.facts["lines"] = {
        "covered": covered,
        "missed": missed,
        "percent": percentage(covered, missed),
    }
    collector.facts["branches"] = {
        "covered": branches["covered"],
        "missed": branches["missed"],
        "percent": percentage(branches["covered"], branches["missed"]),
    } if branches["seen"] else None
    collector.facts["files"] = len(summaries)
    collector.facts["byFile"] = dict(ranked[:limit])
    collector.facts["dropped"] = max(0, len(ranked) - limit)
