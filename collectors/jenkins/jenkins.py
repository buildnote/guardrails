#!/usr/bin/env python3
from guardrail import Collector

import re

MAX_BODY = 2000

DEFAULT_JENKINSFILES = ",".join([
    "Jenkinsfile",
    "Jenkinsfile.*",
    "*.Jenkinsfile",
])

SHELL_STEPS = ("sh", "bat", "powershell", "pwsh")

MINUTES = {
    "SECONDS": 1.0 / 60,
    "MINUTES": 1.0,
    "HOURS": 60.0,
    "DAYS": 60.0 * 24,
}

PIPELINE = re.compile(r"(?<![\w.$])pipeline\s*\{")

STRING = re.compile(
    r"'''(.*?)'''|\"\"\"(.*?)\"\"\"|'([^'\\\n]*(?:\\.[^'\\\n]*)*)'|\"([^\"\\\n]*(?:\\.[^\"\\\n]*)*)\"",
    re.DOTALL,
)

IDENTIFIER = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)")

DECLARATION = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s*$", re.DOTALL)

ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")

AGENT = re.compile(r"^agent\s+(\S.*)$", re.DOTALL)

TIMEOUT = re.compile(r"(?<![\w.$])timeout\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)")

TIME = re.compile(r"time\s*:\s*(\d+)")

UNIT = re.compile(r"unit\s*:\s*['\"]([A-Za-z]+)['\"]")

BARE_TIME = re.compile(r"^\s*(\d+)\s*$")

SCRIPT_ARGUMENT = re.compile(r"script\s*:")

LIBRARY_ANNOTATION = re.compile(r"@Library\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)")

LIBRARY_STEP = re.compile(r"(?<![\w.$@])library\s*\(?\s*(?:identifier\s*:\s*)?['\"]([^'\"]+)['\"]")

CREDENTIAL = re.compile(
    r"(?<![\w.$])credentials\s*\(\s*['\"]([^'\"]+)['\"]\s*\)|credentialsId\s*:\s*['\"]([^'\"]+)['\"]"
)

SHA = re.compile(r"^[0-9a-fA-F]{40}$")

VERSION = re.compile(r"^v?\d+(?:\.\d+)*(?:[-.+][0-9A-Za-z.\-]+)?$")


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def unique(values):
    found = []

    for value in values:
        if value not in found:
            found.append(value)

    return found


def collapsed(text):
    return re.sub(r"\s+", " ", text).strip()


def truncated(text):
    if text is None:
        return None

    return text[:MAX_BODY]


def is_jenkinsfile(path):
    name = path.replace("\\", "/").rsplit("/", 1)[-1]

    return name == "Jenkinsfile" or name.startswith("Jenkinsfile.") or name.endswith(".Jenkinsfile")


def code_mask(text):
    size = len(text)
    mask = bytearray(b"\x01" * size)
    index = 0

    while index < size:
        pair = text[index:index + 2]
        triple = text[index:index + 3]

        if pair == "//":
            found = text.find("\n", index)
            end = size if found < 0 else found
        elif pair == "/*":
            found = text.find("*/", index + 2)
            end = size if found < 0 else found + 2
        elif triple in ("'''", '"""'):
            found = text.find(triple, index + 3)
            end = size if found < 0 else found + 3
        elif text[index] in "'\"":
            quote = text[index]
            cursor = index + 1

            while cursor < size and text[cursor] != "\n":
                if text[cursor] == "\\":
                    cursor += 2
                    continue

                if text[cursor] == quote:
                    cursor += 1
                    break

                cursor += 1

            end = min(cursor, size)
        else:
            index += 1
            continue

        for position in range(index, end):
            mask[position] = 0

        index = max(end, index + 1)

    return mask


def block_end(text, mask, opening):
    depth = 0

    for index in range(opening, len(text)):
        if not mask[index]:
            continue

        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1

            if depth == 0:
                return index

    return None


def pieces(text, mask, start, stop):
    found = []
    begin = start

    for index in range(start, stop):
        if mask[index] and text[index] in "\n;":
            statement = text[begin:index].strip()

            if statement:
                found.append(statement)

            begin = index + 1

    statement = text[begin:stop].strip()

    if statement:
        found.append(statement)

    return found


def units_in(text, mask, start, stop):
    units = []
    cursor = start
    index = start

    while index < stop:
        if mask[index] and text[index] == "{":
            end = block_end(text, mask, index)

            if end is None or end > stop:
                break

            header = pieces(text, mask, cursor, index)

            for statement in header[:-1]:
                units.append(("statement", statement, 0, 0))

            units.append(("block", header[-1] if header else "", index + 1, end))
            cursor = end + 1
            index = end + 1
            continue

        index += 1

    for statement in pieces(text, mask, cursor, stop):
        units.append(("statement", statement, 0, 0))

    return units


def declaration_of(header):
    found = DECLARATION.match(header)

    if not found:
        return None, None

    return found.group(1), found.group(2)


def strings_in(text):
    found = []

    for match in STRING.finditer(text or ""):
        value = next((group for group in match.groups() if group is not None), None)

        if value:
            found.append(value)

    return found


def first_string(text):
    found = STRING.search(text or "")

    if not found:
        return None

    return next((group for group in found.groups() if group is not None), None)


def leading_names(statements):
    found = []

    for statement in statements:
        match = IDENTIFIER.match(statement)

        if match:
            found.append(match.group(1))

    return unique(found)


def assigned_names(statements):
    found = []

    for statement in statements:
        match = ASSIGNMENT.match(statement)

        if match:
            found.append(match.group(1))

    return unique(found)


def minutes_in(arguments):
    found = TIME.search(arguments) or BARE_TIME.match(arguments)

    if not found:
        return None

    unit = UNIT.search(arguments)
    factor = MINUTES.get(unit.group(1).upper()) if unit else 1.0

    if factor is None:
        return None

    return int(round(int(found.group(1)) * factor))


def timeout_in(body):
    found = TIMEOUT.search(body)

    if not found:
        return None, None

    return collapsed(found.group(0)), minutes_in(found.group(1))


def library_of(value, source):
    name, _, ref = value.partition("@")
    ref = ref or None

    return {
        "name": name,
        "ref": ref,
        "pinned": ref is not None and (SHA.match(ref) is not None or VERSION.match(ref) is not None),
        "source": source,
    }


def libraries_in(text):
    found = []

    for match in LIBRARY_ANNOTATION.finditer(text):
        for value in strings_in(match.group(1)):
            found.append(library_of(value, "annotation"))

    for match in LIBRARY_STEP.finditer(text):
        found.append(library_of(match.group(1), "step"))

    return found


def credentials_in(text):
    return unique(named or keyed for named, keyed in CREDENTIAL.findall(text))


def body_of(name, statement):
    if name not in SHELL_STEPS:
        return None

    remainder = statement[len(name):]
    argument = SCRIPT_ARGUMENT.search(remainder)

    return truncated(first_string(remainder[argument.end():] if argument else remainder))


def steps_in(text, mask, start, stop, found):
    for kind, header, begin, end in units_in(text, mask, start, stop):
        if kind == "statement":
            match = IDENTIFIER.match(header)

            if match:
                found.append({"name": match.group(1), "body": body_of(match.group(1), header)})

            continue

        name, _ = declaration_of(header)

        if name:
            found.append({"name": name, "body": None})

        steps_in(text, mask, begin, end, found)


def stages_in(text, mask, start, stop, parent, found):
    for kind, header, begin, end in units_in(text, mask, start, stop):
        if kind != "block":
            continue

        name, arguments = declaration_of(header)

        if name == "stage":
            stage_in(text, mask, first_string(arguments), begin, end, parent, found)
        elif name in ("stages", "parallel"):
            stages_in(text, mask, begin, end, parent, found)


def stage_in(text, mask, name, start, stop, parent, found):
    position = len(found)
    entry = {
        "name": name,
        "parent": parent,
        "agent": None,
        "timeout": None,
        "timeoutMinutes": None,
        "when": False,
        "steps": [],
    }

    found.append(entry)

    for kind, header, begin, end in units_in(text, mask, start, stop):
        if kind == "statement":
            declared = AGENT.match(header)

            if declared:
                entry["agent"] = collapsed(declared.group(1))

            continue

        block, _ = declaration_of(header)

        if block == "agent":
            entry["agent"] = collapsed(text[begin:end])
        elif block == "options":
            entry["timeout"], entry["timeoutMinutes"] = timeout_in(text[begin:end])
        elif block == "when":
            entry["when"] = True
        elif block == "steps":
            steps_in(text, mask, begin, end, entry["steps"])
        elif block in ("stages", "parallel"):
            stages_in(text, mask, begin, end, position, found)


def declarative_of(path, text, mask, start, stop):
    entry = {
        "path": path,
        "style": "declarative",
        "agent": None,
        "timeout": None,
        "timeoutMinutes": None,
        "environment": [],
        "triggers": [],
        "tools": [],
        "libraries": libraries_in(text),
        "credentials": credentials_in(text),
        "stages": [],
    }

    for kind, header, begin, end in units_in(text, mask, start, stop):
        if kind == "statement":
            declared = AGENT.match(header)

            if declared:
                entry["agent"] = collapsed(declared.group(1))

            continue

        block, _ = declaration_of(header)

        if block == "agent":
            entry["agent"] = collapsed(text[begin:end])
        elif block == "options":
            entry["timeout"], entry["timeoutMinutes"] = timeout_in(text[begin:end])
        elif block == "environment":
            entry["environment"] = assigned_names(pieces(text, mask, begin, end))
        elif block == "triggers":
            entry["triggers"] = leading_names(pieces(text, mask, begin, end))
        elif block == "tools":
            entry["tools"] = leading_names(pieces(text, mask, begin, end))
        elif block == "stages":
            stages_in(text, mask, begin, end, None, entry["stages"])

    return entry


def scripted_of(path, text):
    return {
        "path": path,
        "style": "scripted",
        "agent": None,
        "timeout": None,
        "timeoutMinutes": None,
        "environment": [],
        "triggers": [],
        "tools": [],
        "libraries": libraries_in(text),
        "credentials": credentials_in(text),
        "stages": [],
    }


def opening_of(text, mask):
    for found in PIPELINE.finditer(text):
        if mask[found.start()]:
            return found.end() - 1

    return None


with Collector() as collector:
    patterns = globs(collector.input("jenkinsfiles", DEFAULT_JENKINSFILES))

    read = []
    pipelines = []
    unparsed = []

    for path, modified, text in collector.reports(*patterns):
        if not is_jenkinsfile(path):
            continue

        mask = code_mask(text)
        opening = opening_of(text, mask)

        if opening is None:
            read.append({"path": path, "modified": modified, "format": "jenkins"})
            pipelines.append(scripted_of(path, text))
            continue

        closing = block_end(text, mask, opening)

        if closing is None:
            reason = "the pipeline block on line %d is never closed" % (text.count("\n", 0, opening) + 1)
            unparsed.append({"path": path, "reason": reason})
            collector.log("%s was not read: %s" % (path, reason))
            continue

        read.append({"path": path, "modified": modified, "format": "jenkins"})
        pipelines.append(declarative_of(path, text, mask, opening + 1, closing))

    if not read:
        collector.facts["unparsed"] = unparsed
        collector.empty(
            "no Jenkinsfile could be read; see unparsed" if unparsed
            else "no Jenkinsfile matched %s" % ", ".join(patterns)
        )

    collector.sourced("report", read)
    collector.facts["scanned"] = [entry["path"] for entry in read]
    collector.facts["pipelines"] = pipelines
    collector.facts["counts"] = {
        "pipelines": len(pipelines),
        "stages": sum(len(entry["stages"]) for entry in pipelines),
        "steps": sum(len(stage["steps"]) for entry in pipelines for stage in entry["stages"]),
    }
    collector.facts["unparsed"] = unparsed
