#!/usr/bin/env python3
import hashlib
import json
import os
import re
import tempfile

from guardrail import Collector

SEVERITIES = ["critical", "high", "medium", "low", "info", "unknown"]

MAX_MESSAGE = 500

TOOL_TIMEOUT = 240

GITLEAKS = (
    "detect", "--no-banner", "--redact",
    "--report-format", "sarif",
    "--source", ".",
)

TRUFFLEHOG = ("--json", "--no-update")

SARIF_LEVELS = {"error": "high", "warning": "medium", "note": "low", "none": "info"}

FILE_URI = re.compile(r"^file://[^/]*")


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def asked(configured):
    return configured.strip().lower() in ("true", "yes", "1")


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


def numbered(value):
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


def fingerprint_of(identifier, path, line):
    parts = [identifier or "", path or "", "" if line is None else str(line), ""]

    return hashlib.sha256("|".join(parts).encode("utf-8", "replace")).hexdigest()[:16]


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
    index = numbered(result.get("ruleIndex"))

    if index is None:
        index = numbered(mapping(result.get("rule")).get("index"))

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
        or text_of(mapping(rule.get("shortDescription")).get("text"))

    return carried(
        identifier or text_of(rule.get("id")) or "",
        sarif_severity(result, rule),
        message,
        sarif_path(mapping(physical.get("artifactLocation")).get("uri")),
        numbered(mapping(physical.get("region")).get("startLine")),
    )


def carried(identifier, severity, message, path, line):
    return {
        "id": identifier or "",
        "severity": severity if severity in SEVERITIES else "unknown",
        "message": (message or "")[:MAX_MESSAGE],
        "path": path,
        "line": line,
        "fingerprint": fingerprint_of(identifier, path, line),
    }


def sarif_report(text):
    document = parsed(text)

    if not isinstance(document, dict) or not isinstance(document.get("runs"), list):
        return None

    found = []

    for run in document["runs"]:
        driver = mapping(mapping(mapping(run).get("tool")).get("driver"))
        rules = listing(driver.get("rules"))
        by_id = dict((mapping(rule).get("id"), rule) for rule in rules if text_of(mapping(rule).get("id")))

        for result in listing(mapping(run).get("results")):
            found.append(sarif_finding(mapping(result), rules, by_id))

    return found


def gitleaks_report(text):
    document = parsed(text)

    if not isinstance(document, list) or any(not isinstance(entry, dict) for entry in document):
        return None

    if document and not any("RuleID" in entry or "Description" in entry for entry in document):
        return None

    return [
        carried(
            text_of(entry.get("RuleID")),
            "high",
            text_of(entry.get("Description")),
            text_of(entry.get("File")),
            numbered(entry.get("StartLine")),
        )
        for entry in document
    ]


def trufflehog_location(entry):
    data = mapping(mapping(entry.get("SourceMetadata")).get("Data"))

    for source in data.values():
        source = mapping(source)
        path = text_of(source.get("file"))

        if path:
            return path, numbered(source.get("line"))

    return None, None


def trufflehog_finding(entry):
    detector = text_of(entry.get("DetectorName")) or "secret"
    verified = entry.get("Verified") is True
    path, line = trufflehog_location(entry)

    return carried(
        detector,
        "critical" if verified else "high",
        "%s credential detected%s" % (detector, " and verified against the service" if verified else ""),
        path,
        line,
    )


def trufflehog_report(text):
    found = []

    for line in text.splitlines():
        entry = parsed(line)

        if isinstance(entry, dict) and "DetectorName" in entry:
            found.append(trufflehog_finding(entry))

    return found or None


def baseline_report(text):
    document = parsed(text)

    if not isinstance(document, dict) or not isinstance(document.get("results"), dict):
        return None

    found = []

    for name, entries in document["results"].items():
        for entry in listing(entries):
            entry = mapping(entry)
            kind = text_of(entry.get("type"))
            found.append(carried(
                kind,
                "critical" if entry.get("is_verified") is True else "high",
                "%s detected by detect-secrets" % (kind or "secret"),
                text_of(entry.get("filename")) or name,
                numbered(entry.get("line_number")),
            ))

    return found


READERS = [
    ("sarif", sarif_report),
    ("gitleaks", gitleaks_report),
    ("detect-secrets", baseline_report),
    ("trufflehog", trufflehog_report),
]


def ingested(text):
    for format, reader in READERS:
        found = reader(text)

        if found is not None:
            return format, found

    return None, None


def counted(findings):
    counts = dict((severity, 0) for severity in SEVERITIES)

    for finding in findings:
        counts[finding["severity"]] += 1

    return counts


def arguments_for(name, history, report):
    if name == "gitleaks":
        arguments = GITLEAKS + ("--report-path", report)

        return arguments if history else arguments + ("--no-git",)

    return (("git", "file://.") if history else ("filesystem", ".")) + TRUFFLEHOG


def invoked(collector, history, patterns):
    for name in ["gitleaks", "trufflehog"]:
        tool = collector.tool(name)

        if tool is None:
            continue

        handle, report = tempfile.mkstemp(prefix="buildnote-secrets", suffix=".sarif")
        os.close(handle)

        try:
            result = tool.run(*arguments_for(name, history, report), timeout=TOOL_TIMEOUT)

            if result is None:
                collector.empty("%s at %s did not run to completion" % (name, tool.path))

            printed = collector.read(report) if name == "gitleaks" else None
        finally:
            if os.path.exists(report):
                os.remove(report)

        format, found = ingested(printed or result.stdout)

        if found is None:
            collector.empty(
                "%s exited with %d and printed nothing this collector could read"
                % (name, result.returncode)
            )

        collector.log("%s printed a %s report with %d findings" % (name, format, len(found)))

        return found

    collector.empty(
        "no readable secret report matched %s, and neither gitleaks nor trufflehog is on the PATH: "
        "install gitleaks with `brew install gitleaks`, or leave a report in the checkout"
        % ", ".join(patterns)
    )


with Collector() as collector:
    patterns = globs(collector.input("reports", "gitleaks*.sarif,gitleaks*.json,trufflehog*.json,.secrets.baseline"))
    limit = int(collector.input("maxFindings", "200") or "200")
    history = asked(collector.input("scanHistory", "false"))

    read = []
    findings = []

    for path, modified, text in collector.reports(*patterns):
        format, found = ingested(text)

        if found is None:
            collector.log("%s is not a secret report this collector can read" % path)
            continue

        read.append({"path": path, "modified": modified, "format": format})
        findings += found

    if read:
        collector.sourced("report", read)
    else:
        collector.facts["reports"] = []
        findings = invoked(collector, history, patterns)

    collector.facts["counts"] = {"total": len(findings), "bySeverity": counted(findings)}
    collector.facts["findings"] = findings[:limit]
    collector.facts["dropped"] = max(0, len(findings) - limit)
