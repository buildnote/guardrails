#!/usr/bin/env python3
from guardrail import Collector

import re

import guardrail_yaml

MAX_SCRIPT = 2000

DEFAULT_PIPELINES = ",".join([
    "azure-pipelines*.yml",
    "azure-pipelines*.yaml",
])

TRIGGERS = ("trigger", "pr", "schedules", "resources")

SHELLS = ("bash", "pwsh", "powershell", "script")

MACRO = re.compile(r"\$\(([^)]*)\)")

TEMPLATE_EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)

RUNTIME_EXPRESSION = re.compile(r"\$\[(.*?)\]", re.DOTALL)


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


def is_yaml(path):
    return path.replace("\\", "/").rsplit("/", 1)[-1].endswith((".yml", ".yaml"))


def variable_names(value):
    if isinstance(value, dict):
        return list(value.keys())

    if not isinstance(value, list):
        return []

    names = []

    for item in value:
        if isinstance(item, dict):
            for key in ("name", "group", "template"):
                if isinstance(item.get(key), str):
                    names.append(item[key])
                    break

    return names


def names_in(value):
    if isinstance(value, str):
        return [value]

    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str)]


def expressions_in(pattern, body):
    if not body:
        return []

    return unique(found.strip() for found in pattern.findall(body))


def task_reference(task):
    if not task:
        return None, None

    if "@" in task:
        name, version = task.rsplit("@", 1)

        return name or None, version or None

    return task, None


def body_of(declared):
    for shell in SHELLS:
        if shell in declared:
            return text_of(declared.get(shell)), None if shell == "script" else shell

    return None, None


def step_of(declared):
    body, shell = body_of(declared)
    task = text_of(declared.get("task"))
    name, version = task_reference(task)
    inputs = declared.get("inputs")

    return {
        "displayName": text_of(declared.get("displayName")),
        "task": task,
        "taskName": name,
        "taskVersion": version,
        "template": text_of(declared.get("template")),
        "script": truncated(body),
        "shell": shell,
        "inputKeys": list(inputs.keys()) if isinstance(inputs, dict) else [],
        "macros": expressions_in(MACRO, body),
        "templateExpressions": expressions_in(TEMPLATE_EXPRESSION, body),
        "runtimeExpressions": expressions_in(RUNTIME_EXPRESSION, body),
    }


def pool_of(declared):
    pool = declared.get("pool")

    if isinstance(pool, dict) and isinstance(pool.get("vmImage"), str):
        return pool, pool["vmImage"], False

    if isinstance(pool, (dict, str)):
        return pool, None, None

    return None, None, None


def job_of(declared, stage):
    steps = declared.get("steps")
    pool, image, self_hosted = pool_of(declared)

    return {
        "id": text_of(declared.get("job") or declared.get("deployment") or stage),
        "displayName": text_of(declared.get("displayName")),
        "stage": stage,
        "pool": pool,
        "hostedImage": image,
        "selfHosted": self_hosted,
        "timeoutInMinutes": declared.get("timeoutInMinutes"),
        "environment": declared.get("environment"),
        "dependsOn": names_in(declared.get("dependsOn")),
        "condition": text_of(declared.get("condition")),
        "template": text_of(declared.get("template")),
        "steps": [step_of(it) for it in steps if isinstance(it, dict)] if isinstance(steps, list) else [],
    }


def jobs_in(value, stage):
    if not isinstance(value, list):
        return []

    return [job_of(declared, stage) for declared in value if isinstance(declared, dict)]


def pipeline_of(path, document):
    jobs = []
    stages = []
    declared_stages = document.get("stages")

    if isinstance(declared_stages, list):
        for entry in declared_stages:
            if not isinstance(entry, dict):
                continue

            stage = text_of(entry.get("stage"))
            stages.append(stage)
            jobs += jobs_in(entry.get("jobs"), stage)

    jobs += jobs_in(document.get("jobs"), None)

    if not jobs and isinstance(document.get("steps"), list):
        jobs.append(job_of({"steps": document.get("steps")}, None))

    return {
        "path": path,
        "name": text_of(document.get("name")),
        "triggers": [trigger for trigger in TRIGGERS if trigger in document],
        "variables": variable_names(document.get("variables")),
        "stages": [stage for stage in stages if stage is not None],
        "jobs": jobs,
    }


with Collector() as collector:
    patterns = globs(collector.input("pipelines", DEFAULT_PIPELINES))

    read = []
    pipelines = []
    unparsed = []

    for path, modified, text in collector.reports(*patterns):
        if not is_yaml(path):
            continue

        reason = guardrail_yaml.unsupported(text)
        document = None if reason else guardrail_yaml.parse(text)

        if reason is None and not isinstance(document, dict):
            reason = "the document is not a mapping"

        if reason is not None:
            unparsed.append({"path": path, "reason": reason})
            collector.log("%s was not read: %s" % (path, reason))
            continue

        read.append({"path": path, "modified": modified, "format": "azure"})
        pipelines.append(pipeline_of(path, document))

    if not read:
        collector.facts["unparsed"] = unparsed
        collector.empty(
            "no Azure Pipelines definition could be read; see unparsed" if unparsed
            else "no Azure Pipelines definition matched %s" % ", ".join(patterns)
        )

    collector.sourced("report", read)
    collector.facts["pipelines"] = pipelines
    collector.facts["stages"] = unique(sum((entry["stages"] for entry in pipelines), []))
    collector.facts["counts"] = {
        "pipelines": len(pipelines),
        "jobs": sum(len(entry["jobs"]) for entry in pipelines),
        "steps": sum(len(job["steps"]) for entry in pipelines for job in entry["jobs"]),
    }
    collector.facts["unparsed"] = unparsed
