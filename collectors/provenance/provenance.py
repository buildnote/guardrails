#!/usr/bin/env python3
import base64
import json

from guardrail import Collector

INTOTO = "intoto"

REPORTS = "*.intoto.jsonl,*.att.json,attestation*.json,provenance*.json,*.dsse.json"

DIGEST_ORDER = ["gitCommit", "sha256", "sha1", "sha512"]


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def documents(text):
    try:
        json.loads(text)

        return [text]
    except ValueError:
        return [line for line in text.splitlines() if line.strip()]


def enveloped(chunk):
    document = json.loads(chunk)

    return "predicateType" not in document and "subject" not in document


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


def intoto_payload(document):
    encoded = text_of(document.get("payload"))
    if not encoded:
        return None
    for decode in [base64.b64decode, base64.urlsafe_b64decode]:
        try:
            return json.loads(decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8"))
        except (ValueError, TypeError, UnicodeDecodeError):
            continue

    return None


def intoto_statement(document):
    if "predicateType" in document or "subject" in document:
        return document
    payload = mapping(intoto_payload(document))

    return payload if "predicateType" in payload or "subject" in payload else None


def intoto_subjects(subjects):
    found = []
    for subject in subjects:
        subject = mapping(subject)
        digest = mapping(subject.get("digest"))
        found.append({
            "name": text_of(subject.get("name")) or "",
            "digest": dict((key, value) for key, value in digest.items() if isinstance(value, str)),
        })

    return found


def intoto_builder(predicate):
    for holder in [mapping(mapping(predicate.get("runDetails")).get("builder")), mapping(predicate.get("builder"))]:
        identifier = text_of(holder.get("id"))
        if identifier:
            return identifier

    return None


def digest_of(digest):
    for algorithm in DIGEST_ORDER:
        value = text_of(digest.get(algorithm))
        if value:
            return value
    for value in digest.values():
        if text_of(value):
            return value

    return None


def intoto_sources(predicate):
    definition = mapping(predicate.get("buildDefinition"))
    external = mapping(definition.get("externalParameters"))
    candidates = [mapping(external.get("source")), mapping(mapping(predicate.get("invocation")).get("configSource"))]
    candidates += [mapping(it) for it in listing(definition.get("resolvedDependencies"))]
    candidates += [mapping(it) for it in listing(predicate.get("materials"))]

    return candidates


def intoto_source(predicate):
    for holder in intoto_sources(predicate):
        uri = text_of(holder.get("uri"))
        if uri:
            return uri, digest_of(mapping(holder.get("digest")))

    return None, None


def intoto(text):
    document = parsed(text)
    if not isinstance(document, dict):
        return None
    statement = intoto_statement(document)
    if statement is None:
        return None

    predicate = mapping(statement.get("predicate"))
    source, digest = intoto_source(predicate)

    return {
        "predicateType": text_of(statement.get("predicateType")),
        "subjects": intoto_subjects(listing(statement.get("subject"))),
        "builder": intoto_builder(predicate),
        "sourceUri": source,
        "sourceDigest": digest,
    }


def detect(text):
    document = parsed(text)
    if not isinstance(document, dict):
        return None
    schema = text_of(document.get("$schema")) or ""
    if "sarif" in schema.lower() or isinstance(document.get("runs"), list):
        return None
    if text_of(document.get("bomFormat")) == "CycloneDX" or "spdxVersion" in document:
        return None
    if "predicateType" in document or text_of(document.get("payloadType")):
        return INTOTO

    return None


with Collector() as collector:
    patterns = globs(collector.input("reports", REPORTS))

    read = []
    attestations = []

    for path, modified, text in collector.reports(*patterns):
        found = []

        for chunk in documents(text):
            if detect(chunk) != INTOTO:
                continue

            statement = intoto(chunk)

            if statement is None:
                collector.log("%s carries an attestation that could not be read" % path)
                continue

            statement["envelope"] = enveloped(chunk)
            found.append(statement)

        if not found:
            continue

        read.append({"path": path, "modified": modified, "format": INTOTO})
        attestations += found

    if not read:
        collector.empty("no attestation matched %s" % ", ".join(patterns))

    collector.sourced("report", read)
    collector.facts["counts"] = {
        "total": len(attestations),
        "signed": len([it for it in attestations if it["envelope"]]),
    }
    collector.facts["attestations"] = attestations
