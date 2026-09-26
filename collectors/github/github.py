#!/usr/bin/env python3
from guardrail import Collector

import json
import re

import guardrail_yaml

MAX_RUN = 2000

DEFAULT_WORKFLOWS = ",".join([
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
])

CODEOWNERS_LOCATIONS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")

DEFAULT_OWNED_PATHS = "README.md,LICENSE"

ACCOUNT = re.compile(r"@[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?")

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

UNTRUSTED = ("pull_request_target", "issue_comment", "workflow_run")

HOSTED_IMAGES = ("ubuntu-", "windows-", "macos-")

SHA = re.compile(r"^[0-9a-fA-F]{40}$")

INTERPOLATION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)

SECRET = re.compile(r"secrets\s*\.\s*([A-Za-z_][A-Za-z0-9_\-]*)")

INDEXED_SECRET = re.compile(r"secrets\s*\[\s*['\"]([^'\"]+)['\"]\s*\]")


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def unique(values):
    found = []

    for value in values:
        if value not in found:
            found.append(value)

    return found


def text_of(value):
    if value is None or isinstance(value, str):
        return value

    if value is True:
        return "true"

    if value is False:
        return "false"

    return str(value)


def truncated(text):
    if text is None:
        return None

    return text[:MAX_RUN]


def is_workflow(path):
    normalised = path.replace("\\", "/")

    return normalised.startswith(".github/workflows/") and normalised.endswith((".yml", ".yaml"))


def trigger_names(value):
    if value is None:
        return []

    if isinstance(value, dict):
        return list(value.keys())

    if isinstance(value, list):
        return [text_of(item) for item in value if item is not None]

    return [text_of(value)]


def names_in(value):
    if isinstance(value, str):
        return [value]

    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str)]


def interpolations_in(body):
    if not body:
        return []

    return unique(found.strip() for found in INTERPOLATION.findall(body))


def secrets_in(job):
    names = []

    for expression in INTERPOLATION.findall(json.dumps(job, default=str)):
        names += SECRET.findall(expression) + INDEXED_SECRET.findall(expression)

    declared = job.get("secrets")

    if isinstance(declared, dict):
        names += list(declared.keys())

    return unique(names)


def labels_of(value):
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [label for label in value if isinstance(label, str)]

    if isinstance(value, dict):
        return labels_of(value.get("labels"))

    return []


def self_hosted(value):
    labels = labels_of(value)

    if not labels or any("${{" in label for label in labels):
        return None

    if any(label.lower() == "self-hosted" for label in labels):
        return True

    return not any(label.lower().startswith(HOSTED_IMAGES) for label in labels)


def reference(uses):
    if not uses:
        return None, None, False, False

    local = uses.startswith("./") or uses.startswith("../")
    docker = uses.startswith("docker://")
    target = uses[len("docker://"):] if docker else uses

    if "@" in target:
        action, ref = target.rsplit("@", 1)

        return action or None, ref or None, local, docker

    return target or None, None, local, docker


def step_of(declared):
    uses = text_of(declared.get("uses"))
    run = text_of(declared.get("run"))
    inputs = declared.get("with")
    action, ref, local, docker = reference(uses)

    return {
        "name": text_of(declared.get("name")),
        "uses": uses,
        "action": action,
        "ref": ref,
        "pinned": ref is not None and SHA.match(ref) is not None,
        "local": local,
        "docker": docker,
        "run": truncated(run),
        "shell": text_of(declared.get("shell")),
        "withKeys": list(inputs.keys()) if isinstance(inputs, dict) else [],
        "interpolations": interpolations_in(run),
    }


def job_of(id, declared):
    steps = declared.get("steps")

    return {
        "id": id,
        "name": text_of(declared.get("name")),
        "runsOn": declared.get("runs-on"),
        "selfHosted": self_hosted(declared.get("runs-on")),
        "permissions": declared.get("permissions"),
        "timeoutMinutes": declared.get("timeout-minutes"),
        "environment": declared.get("environment"),
        "needs": names_in(declared.get("needs")),
        "if": text_of(declared.get("if")),
        "uses": text_of(declared.get("uses")),
        "secretsUsed": secrets_in(declared),
        "steps": [step_of(it) for it in steps if isinstance(it, dict)] if isinstance(steps, list) else [],
    }


def workflow_of(path, document):
    jobs = document.get("jobs")

    return {
        "path": path,
        "name": text_of(document.get("name")),
        "triggers": trigger_names(document.get("on")),
        "permissions": document.get("permissions"),
        "defaults": document.get("defaults"),
        "concurrency": "concurrency" in document,
        "jobs": [job_of(id, it) for id, it in jobs.items() if isinstance(it, dict)] if isinstance(jobs, dict) else [],
    }


def untrusted_in(workflows):
    found = []

    for workflow in workflows:
        for trigger in workflow["triggers"]:
            if trigger in UNTRUSTED:
                found.append({"path": workflow["path"], "trigger": trigger})

    return found


def account(token):
    return ACCOUNT.fullmatch(token) is not None or EMAIL.fullmatch(token) is not None


def owned_path(path):
    stripped = path.strip()

    while stripped.startswith("./"):
        stripped = stripped[2:]

    return stripped.lstrip("/")


def literal(segment):
    regex = ""

    for character in segment:
        if character == "*":
            regex += "[^/]*"
        elif character == "?":
            regex += "[^/]"
        else:
            regex += re.escape(character)

    return regex


def matcher_for(pattern):
    body = pattern.strip("/")

    if not body:
        return None

    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    segments = (body + "/**" if pattern.endswith("/") else body).split("/")
    regex = "" if anchored else "(?:.*/)?"
    separated = False

    for index, segment in enumerate(segments):
        if segment == "**":
            trailing = index == len(segments) - 1
            regex += ("/" if separated else "") + (".*" if trailing else "(?:.*/)?")
            separated = False
            continue

        regex += ("/" if separated else "") + literal(segment)
        separated = True

    return re.compile(regex)


def ownership_rules_in(text):
    rules = []
    unparsed = []

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0].strip()

        if not stripped:
            continue

        tokens = stripped.split()
        unowned = [token for token in tokens[1:] if not account(token)]

        if unowned:
            unparsed.append({
                "line": number,
                "reason": "'%s' is not a GitHub user, a GitHub team or an email address" % unowned[0],
            })
        else:
            rules.append({"pattern": tokens[0], "owners": tokens[1:], "line": number})

    return rules, unparsed


def last_matching(matchers, path):
    found = None

    for rule, matcher in matchers:
        if matcher is not None and matcher.fullmatch(path):
            found = rule

    return found


def owner_counts(rules):
    counts = {}

    for rule in rules:
        for named in rule["owners"]:
            counts[named] = counts.get(named, 0) + 1

    return counts


def codeowners_of(location, text, asked):
    rules, unparsed = ownership_rules_in(text)
    matchers = [(rule, matcher_for(rule["pattern"])) for rule in rules]
    matched = {}

    for entry in asked.split(","):
        path = entry.strip()

        if not path or path in matched:
            continue

        rule = last_matching(matchers, owned_path(path))
        matched[path] = {
            "owners": rule["owners"] if rule else [],
            "rule": rule["pattern"] if rule else None,
            "line": rule["line"] if rule else None,
        }

    return {
        "path": location,
        "rules": rules,
        "owners": owner_counts(rules),
        "matched": matched,
        "unparsed": unparsed,
    }


with Collector() as collector:
    patterns = globs(collector.input("workflows", DEFAULT_WORKFLOWS))

    read = []
    workflows = []
    unparsed = []

    for path, modified, text in collector.reports(*patterns):
        if not is_workflow(path):
            continue

        reason = guardrail_yaml.unsupported(text)
        document = None if reason else guardrail_yaml.parse(text)

        if reason is None and not isinstance(document, dict):
            reason = "the document is not a mapping"

        if reason is not None:
            unparsed.append({"path": path, "reason": reason})
            collector.log("%s was not read: %s" % (path, reason))
            continue

        read.append({"path": path, "modified": modified, "format": "workflow"})
        workflows.append(workflow_of(path, document))

    owned = dict((path, (modified, text)) for path, modified, text in collector.reports("CODEOWNERS"))
    location = next((path for path in CODEOWNERS_LOCATIONS if path in owned), None)

    if location is not None:
        modified, text = owned[location]
        read.append({"path": location, "modified": modified, "format": "codeowners"})

    if not read:
        collector.facts["unparsed"] = unparsed
        collector.empty(
            "no workflow could be read; see unparsed" if unparsed
            else "no workflow matched %s and no CODEOWNERS file at %s"
            % (", ".join(patterns), ", ".join(CODEOWNERS_LOCATIONS))
        )

    collector.sourced("report", read)

    if workflows:
        collector.facts["workflows"] = workflows
        collector.facts["triggers"] = unique(sum((entry["triggers"] for entry in workflows), []))
        collector.facts["untrustedTriggers"] = untrusted_in(workflows)
        collector.facts["counts"] = {
            "workflows": len(workflows),
            "jobs": sum(len(entry["jobs"]) for entry in workflows),
            "steps": sum(len(job["steps"]) for entry in workflows for job in entry["jobs"]),
        }

    if location is not None:
        collector.facts["codeowners"] = codeowners_of(
            location, owned[location][1], collector.input("paths", DEFAULT_OWNED_PATHS)
        )

    collector.facts["unparsed"] = unparsed
