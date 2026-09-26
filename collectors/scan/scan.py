#!/usr/bin/env python3
import hashlib
import json
import re

from guardrail import Collector

SEVERITIES = ["critical", "high", "medium", "low", "info", "unknown"]

KINDS = ["sast", "sca", "secret", "iac", "container", "unknown"]

MAX_MESSAGE = 500

SARIF_LEVELS = {"error": "high", "warning": "medium", "note": "low", "none": "info"}

NAMED_SEVERITIES = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "moderate": "medium",
    "low": "low",
    "negligible": "low",
    "unknown": "unknown",
}

SECRET_DRIVERS = re.compile(r"gitleaks|trufflehog", re.IGNORECASE)
IAC_DRIVERS = re.compile(r"checkov|tfsec|terrascan|kics", re.IGNORECASE)
SCA_DRIVERS = re.compile(r"trivy|grype|snyk", re.IGNORECASE)

FILE_URI = re.compile(r"^file://[^/]*")
IDENTIFIER = re.compile(r"CVE-\d{4}-\d{4,}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", re.IGNORECASE)


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def counted(findings, key, names):
    counts = dict((name, 0) for name in names)

    for finding in findings:
        name = finding.get(key)
        counts[name if name in counts else "unknown"] += 1

    return counts


def shortened(finding):
    message = finding.get("message") or ""

    if len(message) > MAX_MESSAGE:
        finding["message"] = message[:MAX_MESSAGE]

    return finding


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


def unique(values):
    found = []
    for value in values:
        if value and value not in found:
            found.append(value)

    return found


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


def named_severity(value):
    if not isinstance(value, str):
        return "unknown"

    return NAMED_SEVERITIES.get(value.strip().lower(), "unknown")


def fingerprint_of(identifier, path, line, package):
    named = mapping(package)
    described = "%s@%s" % (text_of(named.get("name")) or "", text_of(named.get("version")) or "") if named else ""
    parts = [identifier or "", path or "", "" if line is None else str(line), described]

    return hashlib.sha256("|".join(parts).encode("utf-8", "replace")).hexdigest()[:16]


def stamped(found):
    found["fingerprint"] = fingerprint_of(found["id"], found["path"], found["line"], found["package"])

    return found


def package_of(name, version):
    return {"name": name, "version": version or ""} if name else None


def identifiers_in(values):
    found = []
    for value in values:
        for identifier in IDENTIFIER.findall(value or ""):
            if identifier not in found:
                found.append(identifier)

    return found


def sarif_kind(name):
    if SECRET_DRIVERS.search(name):
        return "secret"
    if IAC_DRIVERS.search(name):
        return "iac"
    if SCA_DRIVERS.search(name):
        return "sca"

    return "sast"


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


def sarif_location(result):
    locations = listing(result.get("locations"))

    return mapping(mapping(locations[0]).get("physicalLocation")) if locations else {}


def sarif_finding(result, rules, by_id, kind):
    identifier = text_of(result.get("ruleId")) or text_of(mapping(result.get("rule")).get("id"))
    rule = sarif_rule(result, rules, by_id, identifier)
    identifier = identifier or text_of(rule.get("id")) or ""
    physical = sarif_location(result)
    message = text_of(mapping(result.get("message")).get("text")) \
        or text_of(mapping(rule.get("shortDescription")).get("text")) \
        or ""
    tags = [text_of(tag) for tag in listing(mapping(rule.get("properties")).get("tags"))]

    return stamped({
        "id": identifier,
        "severity": sarif_severity(result, rule),
        "message": message,
        "path": sarif_path(mapping(physical.get("artifactLocation")).get("uri")),
        "line": numbered(mapping(physical.get("region")).get("startLine")),
        "kind": kind,
        "package": None,
        "identifiers": identifiers_in([identifier, message] + tags),
        "fixedIn": None,
    })


def sarif(text):
    document = parsed(text)
    if not isinstance(document, dict) or not isinstance(document.get("runs"), list):
        return None

    tool = None
    findings = []
    for run in listing(document.get("runs")):
        driver = mapping(mapping(mapping(run).get("tool")).get("driver"))
        rules = listing(driver.get("rules"))
        by_id = dict((mapping(rule).get("id"), rule) for rule in rules if text_of(mapping(rule).get("id")))
        name = text_of(driver.get("name")) or ""
        if tool is None and name:
            tool = {
                "name": name,
                "version": text_of(driver.get("version")) or text_of(driver.get("semanticVersion")),
            }
        kind = sarif_kind(name)
        for result in listing(mapping(run).get("results")):
            findings.append(sarif_finding(mapping(result), rules, by_id, kind))

    return {"tool": tool, "findings": findings}


def trivy_vulnerability(entry, target, scanned):
    identifier = text_of(entry.get("VulnerabilityID")) or ""

    return stamped({
        "id": identifier,
        "severity": named_severity(entry.get("Severity")),
        "message": text_of(entry.get("Title")) or text_of(entry.get("Description")) or identifier,
        "path": text_of(entry.get("PkgPath")) or (target if scanned != "os-pkgs" else None),
        "line": None,
        "kind": "sca",
        "package": package_of(text_of(entry.get("PkgName")), text_of(entry.get("InstalledVersion"))),
        "identifiers": unique([identifier]),
        "fixedIn": text_of(entry.get("FixedVersion")),
    })


def trivy_misconfiguration(entry, target):
    advisory = text_of(entry.get("AVDID"))
    identifier = text_of(entry.get("ID")) or advisory or ""

    return stamped({
        "id": identifier,
        "severity": named_severity(entry.get("Severity")),
        "message": text_of(entry.get("Message")) or text_of(entry.get("Title")) or identifier,
        "path": target,
        "line": numbered(mapping(entry.get("CauseMetadata")).get("StartLine")),
        "kind": "iac",
        "package": None,
        "identifiers": unique([advisory]),
        "fixedIn": None,
    })


def trivy_secret(entry, target):
    identifier = text_of(entry.get("RuleID")) or ""

    return stamped({
        "id": identifier,
        "severity": named_severity(entry.get("Severity")),
        "message": text_of(entry.get("Title")) or identifier,
        "path": target,
        "line": numbered(entry.get("StartLine")),
        "kind": "secret",
        "package": None,
        "identifiers": [],
        "fixedIn": None,
    })


def trivy(text):
    document = parsed(text)
    if not isinstance(document, dict):
        return None
    if "SchemaVersion" not in document and not isinstance(document.get("Results"), list):
        return None

    findings = []
    for result in listing(document.get("Results")):
        result = mapping(result)
        target = text_of(result.get("Target"))
        scanned = text_of(result.get("Class")) or ""
        for entry in listing(result.get("Vulnerabilities")):
            findings.append(trivy_vulnerability(mapping(entry), target, scanned))
        for entry in listing(result.get("Misconfigurations")):
            findings.append(trivy_misconfiguration(mapping(entry), target))
        for entry in listing(result.get("Secrets")):
            findings.append(trivy_secret(mapping(entry), target))

    return {"tool": {"name": "trivy", "version": None}, "findings": findings}


def grype_fix(vulnerability):
    available = [text_of(it) for it in listing(mapping(vulnerability.get("fix")).get("versions"))]

    return unique(available)[0] if unique(available) else None


def grype_finding(match):
    vulnerability = mapping(match.get("vulnerability"))
    artifact = mapping(match.get("artifact"))
    identifier = text_of(vulnerability.get("id")) or ""
    locations = listing(artifact.get("locations"))
    related = [text_of(mapping(it).get("id")) for it in listing(match.get("relatedVulnerabilities"))]

    return stamped({
        "id": identifier,
        "severity": named_severity(vulnerability.get("severity")),
        "message": text_of(vulnerability.get("description")) or identifier,
        "path": text_of(mapping(locations[0]).get("path")) if locations else None,
        "line": None,
        "kind": "sca",
        "package": package_of(text_of(artifact.get("name")), text_of(artifact.get("version"))),
        "identifiers": unique([identifier] + related),
        "fixedIn": grype_fix(vulnerability),
    })


def grype(text):
    document = parsed(text)
    if not isinstance(document, dict) or not isinstance(document.get("matches"), list):
        return None

    descriptor = mapping(document.get("descriptor"))
    tool = {
        "name": text_of(descriptor.get("name")) or "grype",
        "version": text_of(descriptor.get("version")),
    }

    return {"tool": tool, "findings": [grype_finding(mapping(it)) for it in listing(document.get("matches"))]}


def osv_severity(vulnerability, groups, identifier):
    declared = mapping(vulnerability.get("database_specific")).get("severity")
    if isinstance(declared, str):
        return named_severity(declared)
    for group in groups:
        group = mapping(group)
        if identifier not in [text_of(it) for it in listing(group.get("ids"))]:
            continue
        scored = scored_severity(group.get("max_severity"))
        if scored:
            return scored

    return "unknown"


def osv_fix(vulnerability):
    for affected in listing(vulnerability.get("affected")):
        for ranged in listing(mapping(affected).get("ranges")):
            for event in listing(mapping(ranged).get("events")):
                fixed = text_of(mapping(event).get("fixed"))
                if fixed:
                    return fixed

    return None


def osv_finding(vulnerability, named, groups, path):
    identifier = text_of(vulnerability.get("id")) or ""
    aliases = [text_of(it) for it in listing(vulnerability.get("aliases"))]

    return stamped({
        "id": identifier,
        "severity": osv_severity(vulnerability, groups, identifier),
        "message": text_of(vulnerability.get("summary")) or text_of(vulnerability.get("details")) or identifier,
        "path": path,
        "line": None,
        "kind": "sca",
        "package": package_of(text_of(named.get("name")), text_of(named.get("version"))),
        "identifiers": unique([identifier] + aliases),
        "fixedIn": osv_fix(vulnerability),
    })


def osv(text):
    document = parsed(text)
    if not isinstance(document, dict) or not isinstance(document.get("results"), list):
        return None

    findings = []
    for result in listing(document.get("results")):
        result = mapping(result)
        path = text_of(mapping(result.get("source")).get("path"))
        for entry in listing(result.get("packages")):
            entry = mapping(entry)
            named = mapping(entry.get("package"))
            groups = listing(entry.get("groups"))
            for vulnerability in listing(entry.get("vulnerabilities")):
                findings.append(osv_finding(mapping(vulnerability), named, groups, path))

    return {"tool": {"name": "osv-scanner", "version": None}, "findings": findings}


def detect(text):
    document = parsed(text)
    if not isinstance(document, dict):
        return None
    schema = text_of(document.get("$schema")) or ""
    if "sarif" in schema.lower() or isinstance(document.get("runs"), list):
        return "sarif"
    if text_of(document.get("bomFormat")) == "CycloneDX" or "spdxVersion" in document:
        return None
    if "predicateType" in document or text_of(document.get("payloadType")):
        return None
    if "SchemaVersion" in document or isinstance(document.get("Results"), list):
        return "trivy"
    if isinstance(document.get("matches"), list):
        return "grype"
    if isinstance(document.get("results"), list):
        return "osv"

    return None


NORMALIZERS = {"sarif": sarif, "trivy": trivy, "grype": grype, "osv": osv}


with Collector() as collector:
    patterns = globs(collector.input("reports", "*.sarif,*.sarif.json,trivy*.json,grype*.json,osv*.json,semgrep*.json,snyk*.json"))
    limit = int(collector.input("maxFindings", "200") or "200")

    read = []
    findings = []

    for path, modified, text in collector.reports(*patterns):
        format = detect(text)

        if format is None:
            continue

        normalized = NORMALIZERS[format](text)

        if normalized is None:
            collector.log("%s looked like %s and could not be read" % (path, format))
            continue

        found = normalized.get("findings") or []
        producer = normalized.get("tool") or {}

        read.append({
            "path": path,
            "modified": modified,
            "format": format,
            "producer": {"name": producer.get("name"), "version": producer.get("version")},
            "findings": len(found),
        })
        findings += found

    if not read:
        collector.empty("no scanner report matched %s" % ", ".join(patterns))

    collector.sourced("report", read)
    collector.facts["counts"] = dict(counted(findings, "severity", SEVERITIES), total=len(findings))
    collector.facts["kinds"] = counted(findings, "kind", KINDS)
    collector.facts["findings"] = [shortened(finding) for finding in findings[:limit]]
    collector.facts["dropped"] = max(0, len(findings) - limit)
