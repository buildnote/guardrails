#!/usr/bin/env python3
import json
import re
import xml.etree.ElementTree as ElementTree

from guardrail import Collector

REPORTS = "bom.json,bom.xml,*.cdx.json,*.cdx.xml,cyclonedx*.json,cyclonedx*.xml,sbom*.json,*.spdx.json,sbom*.spdx"

NAMESPACE_VERSION = re.compile(r"/bom/([0-9]+\.[0-9]+)")

NOT_A_LICENSE = ["", "NOASSERTION", "NONE"]


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def by_license(components):
    counts = {}

    for component in components:
        for named in component["licenses"]:
            counts[named] = counts.get(named, 0) + 1

    return counts


def parsed(text):
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def rooted(text):
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return ElementTree.fromstring(text)
    except (ElementTree.ParseError, ValueError, TypeError):
        return None


def mapping(value):
    return value if isinstance(value, dict) else {}


def listing(value):
    return value if isinstance(value, list) else []


def text_of(value):
    return value if isinstance(value, str) else None


def local(tag):
    return tag.rpartition("}")[2] if isinstance(tag, str) else ""


def cyclonedx_licenses(licenses):
    found = []
    for entry in licenses:
        entry = mapping(entry)
        declared = mapping(entry.get("license"))
        named = text_of(declared.get("id")) or text_of(declared.get("name")) or text_of(entry.get("expression"))
        if named and named not in found:
            found.append(named)

    return found


def cyclonedx_components(components):
    found = []
    for component in components:
        component = mapping(component)
        name = text_of(component.get("name"))
        if name:
            found.append({
                "name": name,
                "version": text_of(component.get("version")) or "",
                "purl": text_of(component.get("purl")),
                "type": text_of(component.get("type")),
                "licenses": cyclonedx_licenses(listing(component.get("licenses"))),
            })
        found += cyclonedx_components(listing(component.get("components")))

    return found


def cyclonedx_json(document):
    if text_of(document.get("bomFormat")) != "CycloneDX":
        return None

    return {
        "format": "cyclonedx",
        "specVersion": text_of(document.get("specVersion")),
        "components": cyclonedx_components(listing(document.get("components"))),
    }


def child_text(element, name):
    for child in element:
        if local(child.tag) == name:
            return (child.text or "").strip() or None

    return None


def xml_licenses(component):
    found = []
    for group in component:
        if local(group.tag) != "licenses":
            continue
        for entry in group:
            if local(entry.tag) == "expression":
                named = (entry.text or "").strip() or None
            else:
                named = child_text(entry, "id") or child_text(entry, "name")
            if named and named not in found:
                found.append(named)

    return found


def xml_components(parent):
    found = []
    for group in parent:
        if local(group.tag) != "components":
            continue
        for component in group:
            if local(component.tag) != "component":
                continue
            name = child_text(component, "name")
            if name:
                found.append({
                    "name": name,
                    "version": child_text(component, "version") or "",
                    "purl": child_text(component, "purl"),
                    "type": component.get("type"),
                    "licenses": xml_licenses(component),
                })
            found += xml_components(component)

    return found


def xml_spec_version(root):
    declared = root.get("specVersion")
    if declared:
        return declared
    found = NAMESPACE_VERSION.search(root.tag)

    return found.group(1) if found else None


def cyclonedx_xml(text):
    root = rooted(text)
    if root is None or local(root.tag) != "bom":
        return None

    return {"format": "cyclonedx", "specVersion": xml_spec_version(root), "components": xml_components(root)}


def cyclonedx(text):
    document = parsed(text)
    if isinstance(document, dict):
        return cyclonedx_json(document)

    return cyclonedx_xml(text)


def spdx_licenses(values):
    found = []
    for value in values:
        named = (text_of(value) or "").strip()
        if named.upper() in NOT_A_LICENSE or named in found:
            continue
        found.append(named)

    return found


def spdx_purl(references):
    for reference in references:
        reference = mapping(reference)
        if text_of(reference.get("referenceType")) == "purl":
            return text_of(reference.get("referenceLocator"))

    return None


def spdx_json(document):
    if "spdxVersion" not in document and "SPDXID" not in document:
        return None

    components = []
    for entry in listing(document.get("packages")):
        entry = mapping(entry)
        name = text_of(entry.get("name"))
        if not name:
            continue
        purpose = text_of(entry.get("primaryPackagePurpose"))
        components.append({
            "name": name,
            "version": text_of(entry.get("versionInfo")) or "",
            "purl": spdx_purl(listing(entry.get("externalRefs"))),
            "type": purpose.lower() if purpose else None,
            "licenses": spdx_licenses([entry.get("licenseConcluded"), entry.get("licenseDeclared")]),
        })

    return {"format": "spdx", "specVersion": text_of(document.get("spdxVersion")), "components": components}


def tag_value_purl(value):
    parts = value.split()

    return parts[2] if len(parts) >= 3 and parts[1] == "purl" else None


def spdx_tag_value(text):
    if not isinstance(text, str) or "SPDXVersion:" not in text:
        return None

    version = None
    components = []
    current = None
    for line in text.splitlines():
        tag, separator, value = line.partition(":")
        if not separator:
            continue
        tag = tag.strip()
        value = value.strip()
        if tag == "SPDXVersion":
            version = version or value
        elif tag == "PackageName":
            current = {"name": value, "version": "", "purl": None, "type": None, "licenses": []}
            components.append(current)
        elif current is None:
            continue
        elif tag == "PackageVersion":
            current["version"] = value
        elif tag == "PrimaryPackagePurpose":
            current["type"] = value.lower() or None
        elif tag == "ExternalRef":
            current["purl"] = tag_value_purl(value) or current["purl"]
        elif tag in ["PackageLicenseConcluded", "PackageLicenseDeclared"]:
            current["licenses"] = spdx_licenses(current["licenses"] + [value])

    return {"format": "spdx", "specVersion": version, "components": components}


def spdx(text):
    document = parsed(text)
    if isinstance(document, dict):
        return spdx_json(document)

    return spdx_tag_value(text)


def detect(text):
    document = parsed(text)
    if isinstance(document, dict):
        schema = text_of(document.get("$schema")) or ""
        if "sarif" in schema.lower() or isinstance(document.get("runs"), list):
            return None
        if text_of(document.get("bomFormat")) == "CycloneDX":
            return "cyclonedx"
        if "spdxVersion" in document:
            return "spdx"

        return None
    if isinstance(text, str) and "SPDXVersion:" in text:
        return "spdx"
    root = rooted(text)
    if root is not None and local(root.tag) == "bom":
        return "cyclonedx"

    return None


READERS = {"cyclonedx": cyclonedx, "spdx": spdx}


with Collector() as collector:
    patterns = globs(collector.input("reports", REPORTS))
    limit = int(collector.input("maxComponents", "500") or "500")

    read = []
    components = []
    first = None

    for path, modified, text in collector.reports(*patterns):
        format = detect(text)

        if format not in READERS:
            continue

        document = READERS[format](text)

        if document is None:
            collector.log("%s looked like %s and could not be read" % (path, format))
            continue

        if first is None:
            first = document

        read.append({"path": path, "modified": modified, "format": document["format"]})
        components += document["components"]

    if not read:
        collector.empty("no bill of materials matched %s" % ", ".join(patterns))

    collector.sourced("report", read)
    collector.facts["format"] = first["format"]
    collector.facts["specVersion"] = first["specVersion"]
    collector.facts["counts"] = {
        "total": len(components),
        "licensed": len([it for it in components if it["licenses"]]),
        "unlicensed": len([it for it in components if not it["licenses"]]),
    }
    collector.facts["licenses"] = by_license(components)
    collector.facts["components"] = components[:limit]
    collector.facts["dropped"] = max(0, len(components) - limit)
