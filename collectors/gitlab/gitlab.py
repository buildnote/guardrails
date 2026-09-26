#!/usr/bin/env python3
from guardrail import Collector

import re

import guardrail_yaml

MAX_SCRIPT = 2000

DEFAULT_PIPELINES = ",".join([
    ".gitlab-ci.yml",
    ".gitlab-ci.yaml",
])

RESERVED = (
    "stages",
    "types",
    "spec",
    "variables",
    "default",
    "include",
    "workflow",
    "image",
    "services",
    "before_script",
    "after_script",
    "cache",
)

SCRIPTS = ("before_script", "script", "after_script")

VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*([a-z]*)")

MINUTES = {
    "": 1.0 / 60,
    "s": 1.0 / 60,
    "sec": 1.0 / 60,
    "secs": 1.0 / 60,
    "second": 1.0 / 60,
    "seconds": 1.0 / 60,
    "m": 1,
    "min": 1,
    "mins": 1,
    "minute": 1,
    "minutes": 1,
    "h": 60,
    "hr": 60,
    "hrs": 60,
    "hour": 60,
    "hours": 60,
    "d": 60 * 24,
    "day": 60 * 24,
    "days": 60 * 24,
    "w": 60 * 24 * 7,
    "week": 60 * 24 * 7,
    "weeks": 60 * 24 * 7,
}


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

    return text[:MAX_SCRIPT]


def is_pipeline(path):
    return path.replace("\\", "/").rsplit("/", 1)[-1] in (".gitlab-ci.yml", ".gitlab-ci.yaml")


def minutes_in(value):
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(value / 60.0))

    if not isinstance(value, str):
        return None

    found = DURATION.findall(value.lower())

    if not found:
        return None

    total = 0.0

    for amount, unit in found:
        if unit not in MINUTES:
            return None

        total += float(amount) * MINUTES[unit]

    return int(round(total))


def variables_in(body):
    if not body:
        return []

    return unique(braced or bare for braced, bare in VARIABLE.findall(body))


def names_of(value):
    if isinstance(value, dict):
        return list(value.keys())

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]

    if isinstance(value, str):
        return [value]

    return []


def script_body(value):
    if isinstance(value, list):
        lines = []

        for item in value:
            lines += [text_of(it) or "" for it in item] if isinstance(item, list) else [text_of(item) or ""]

        return "\n".join(lines)

    return text_of(value)


def needs_of(value):
    if isinstance(value, str):
        return [value]

    if not isinstance(value, list):
        return []

    names = []

    for item in value:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("job"), str):
            names.append(item["job"])

    return names


def scripts_of(declared):
    found = []

    for section in SCRIPTS:
        if section not in declared:
            continue

        body = script_body(declared.get(section))

        found.append({
            "section": section,
            "run": truncated(body),
            "variables": variables_in(body),
        })

    return found


def rules_of(declared):
    rules = declared.get("rules")

    return len(rules) if isinstance(rules, list) else 0


def job_of(id, declared):
    timeout = declared.get("timeout")

    return {
        "id": id,
        "stage": text_of(declared.get("stage")),
        "image": declared.get("image"),
        "tags": names_of(declared.get("tags")),
        "timeout": text_of(timeout),
        "timeoutMinutes": minutes_in(timeout),
        "environment": declared.get("environment"),
        "needs": needs_of(declared.get("needs")),
        "rules": rules_of(declared),
        "when": text_of(declared.get("when")),
        "allowFailure": declared.get("allow_failure") is True,
        "interruptible": declared.get("interruptible") is True,
        "extends": names_of(declared.get("extends")),
        "trigger": declared.get("trigger"),
        "variables": names_of(declared.get("variables")),
        "secretsUsed": names_of(declared.get("secrets")),
        "scripts": scripts_of(declared),
    }


def is_job(id, declared):
    return isinstance(declared, dict) and id not in RESERVED and not id.startswith(".")


INCLUDE_KEYS = ("local", "project", "template", "remote", "component")


def includes_of(value):
    if value is None:
        return []

    entries = value if isinstance(value, list) else [value]
    found = []

    for entry in entries:
        if isinstance(entry, str):
            found.append(entry)
        elif isinstance(entry, dict):
            for key in INCLUDE_KEYS:
                if isinstance(entry.get(key), str):
                    found.append(entry[key])
                    break

    return found


def workflow_rules_of(document):
    workflow = document.get("workflow")

    if not isinstance(workflow, dict):
        return 0

    rules = workflow.get("rules")

    return len(rules) if isinstance(rules, list) else 0


def pipeline_of(path, document):
    return {
        "path": path,
        "stages": names_of(document.get("stages")),
        "image": document.get("image"),
        "default": document.get("default"),
        "variables": names_of(document.get("variables")),
        "includes": includes_of(document.get("include")),
        "workflowRules": workflow_rules_of(document),
        "jobs": [job_of(id, declared) for id, declared in document.items() if is_job(id, declared)],
    }


CODEOWNERS_LOCATIONS = ("CODEOWNERS", ".gitlab/CODEOWNERS", "docs/CODEOWNERS")

DEFAULT_OWNED_PATHS = "README.md,LICENSE"

DEFAULT_SECTION = "codeowners"

HEADER = re.compile(r"^(\^?)\[([^\[\]]+)\](?:\[(\d+)\])?(.*)$")

HANDLE = re.compile(r"@[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?(?:/[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)*")

ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def account(token):
    return HANDLE.fullmatch(token) is not None or ADDRESS.fullmatch(token) is not None


def owned_path(path):
    trimmed = path.strip().replace("\\", "/")

    while trimmed.startswith("./"):
        trimmed = trimmed[2:]

    return trimmed.lstrip("/")


def expanded(body):
    regex = ""
    index = 0

    while index < len(body):
        closing = body.find("]", index + 1) if body[index] == "[" else -1

        if body.startswith("**/", index):
            regex += "(?:.*/)?"
            index += 3
        elif body.startswith("**", index):
            regex += ".*"
            index += 2
        elif body[index] == "*":
            regex += "[^/]*"
            index += 1
        elif body[index] == "?":
            regex += "[^/]"
            index += 1
        elif closing > index + 1:
            content = body[index + 1:closing]
            regex += "[%s]" % ("^" + content[1:] if content[:1] in ("!", "^") else content)
            index = closing + 1
        else:
            regex += re.escape(body[index])
            index += 1

    return regex


def matcher_for(pattern):
    body = pattern.strip("/")

    if not body:
        return None

    rooted = pattern.startswith("/") or "/" in body

    return re.compile(("" if rooted else "(?:.*/)?") + expanded(body) + "(?:/.*)?")


def section_of(name, optional, approvals, defaults, line, implicit):
    return {
        "name": name,
        "optional": optional,
        "approvalsRequired": approvals,
        "defaultOwners": defaults,
        "line": line,
        "implicit": implicit,
        "rules": [],
    }


def sections_in(text):
    sections = []
    unparsed = []
    section = None
    defaults = []

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0].strip()

        if not stripped:
            continue

        if stripped.startswith("[") or stripped.startswith("^["):
            header = HEADER.match(stripped)

            if header is None:
                unparsed.append({"line": number, "reason": "'%s' is no closed section header" % stripped})
                continue

            tokens = header.group(4).split()
            defaults = [token for token in tokens if account(token)]
            section = section_of(
                header.group(2).strip(),
                header.group(1) == "^",
                int(header.group(3)) if header.group(3) else None,
                defaults,
                number,
                False,
            )
            sections.append(section)

            for token in tokens:
                if not account(token):
                    unparsed.append({
                        "line": number,
                        "reason": "'%s' is no user, group or email address, so the section does not default to it" % token,
                    })

            continue

        tokens = stripped.split()
        unknown = [token for token in tokens[1:] if not account(token)]

        if unknown:
            unparsed.append({
                "line": number,
                "reason": "'%s' is no user, group or email address" % unknown[0],
            })
            continue

        if section is None:
            section = section_of(DEFAULT_SECTION, False, None, [], None, True)
            sections.append(section)

        section["rules"].append({
            "pattern": tokens[0],
            "owners": tokens[1:] or list(defaults),
            "inherited": not tokens[1:] and bool(defaults),
            "line": number,
        })

    return sections, unparsed


def owners_for(sections, path):
    found = []

    for section in sections:
        owning = None

        for rule in section["rules"]:
            compiled = matcher_for(rule["pattern"])

            if compiled is not None and compiled.fullmatch(path):
                owning = rule

        if owning is None:
            continue

        found.append({
            "section": section["name"],
            "optional": section["optional"],
            "approvalsRequired": section["approvalsRequired"],
            "owners": owning["owners"],
            "rule": owning["pattern"],
            "line": owning["line"],
        })

    return found


def owner_counts(sections):
    counts = {}

    for section in sections:
        for rule in section["rules"]:
            for name in rule["owners"]:
                counts[name] = counts.get(name, 0) + 1

    return counts


def codeowners_of(location, text, asked):
    sections, unparsed = sections_in(text)
    matched = {}

    for entry in asked.split(","):
        path = entry.strip()

        if not path or path in matched:
            continue

        owning = owners_for(sections, owned_path(path))
        matched[path] = {
            "owners": unique(sum((entry["owners"] for entry in owning), [])),
            "sections": owning,
        }

    return {
        "path": location,
        "sections": sections,
        "owners": owner_counts(sections),
        "matched": matched,
        "unparsed": unparsed,
    }


with Collector() as collector:
    patterns = globs(collector.input("pipelines", DEFAULT_PIPELINES))

    read = []
    pipelines = []
    unparsed = []

    for path, modified, text in collector.reports(*patterns):
        if not is_pipeline(path):
            continue

        reason = guardrail_yaml.unsupported(text)
        document = None if reason else guardrail_yaml.parse(text)

        if reason is None and not isinstance(document, dict):
            reason = "the document is not a mapping"

        if reason is not None:
            unparsed.append({"path": path, "reason": reason})
            collector.log("%s was not read: %s" % (path, reason))
            continue

        read.append({"path": path, "modified": modified, "format": "gitlab-ci"})
        pipelines.append(pipeline_of(path, document))

    owned = dict((path, (modified, text)) for path, modified, text in collector.reports("CODEOWNERS"))
    location = next((path for path in CODEOWNERS_LOCATIONS if path in owned), None)

    if location is not None:
        read.append({"path": location, "modified": owned[location][0], "format": "codeowners"})

    if not read:
        collector.facts["unparsed"] = unparsed
        collector.empty(
            "no GitLab CI file could be read; see unparsed" if unparsed
            else "no GitLab CI file matched %s and no CODEOWNERS file at %s"
            % (", ".join(patterns), ", ".join(CODEOWNERS_LOCATIONS))
        )

    collector.sourced("report", read)

    if pipelines:
        collector.facts["pipelines"] = pipelines
        collector.facts["stages"] = unique(sum((entry["stages"] for entry in pipelines), []))
        collector.facts["counts"] = {
            "pipelines": len(pipelines),
            "jobs": sum(len(entry["jobs"]) for entry in pipelines),
            "scripts": sum(len(job["scripts"]) for entry in pipelines for job in entry["jobs"]),
        }

    if location is not None:
        collector.facts["codeowners"] = codeowners_of(
            location, owned[location][1], collector.input("paths", DEFAULT_OWNED_PATHS)
        )

    collector.facts["unparsed"] = unparsed
