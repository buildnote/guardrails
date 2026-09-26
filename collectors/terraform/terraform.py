#!/usr/bin/env python3
import json
import os
import re

from guardrail import Collector

SKIPPED = (".git", ".terraform", "node_modules", "__pycache__", ".gradle", ".venv", ".idea")

CONFIGURATION = ("*.tf", "*.tfvars", ".terraform.lock.hcl")

STATE = (".tfstate", ".tfstate.backup")

LOCK_FILE = ".terraform.lock.hcl"

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")

NUMBER = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")

EXACT = re.compile(r"^=?\s*\d+(\.\d+)*([-+][0-9A-Za-z.\-]+)?$")

REGISTRY = re.compile(
    r"^([a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+(:\d+)?/)?[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+(//.+)?$"
)

GIT_PREFIXES = ("git::", "git@", "http://", "https://", "github.com/", "bitbucket.org/", "ssh://")

SECRET_NAMES = (
    "secret", "password", "passphrase", "token", "credential", "access_key",
    "encryption_key", "customer_key", "private_key", "conn_str", "sas",
)

ENCRYPTED_BY = {
    "s3": ("encrypt", ("kms_key_id", "sse_customer_key")),
    "gcs": (None, ("encryption_key", "kms_encryption_key")),
    "oss": (None, ("kms_key_id",)),
}

LOCKED_BY = {
    "s3": ("use_lockfile", ("dynamodb_table",)),
    "consul": ("lock", ()),
    "http": (None, ("lock_address",)),
    "oss": (None, ("tablestore_table",)),
}

MAX_VALUE = 200

ESCAPES = (("\\n", "\n"), ("\\t", "\t"), ("\\r", "\r"), ('\\"', '"'), ("\\\\", "\\"))


class Unreadable(Exception):
    pass


def slashed(path):
    return path.replace(os.sep, "/")


def directory_of(path):
    return os.path.dirname(path) or "."


def normalized(directory):
    cleaned = slashed(os.path.normpath(directory.strip() or "."))

    return cleaned.strip("/") or "." if cleaned not in ("", ".") else "."


def under(prefix, path):
    return prefix == "." or path == prefix or path.startswith(prefix + "/")


def format_of(path):
    name = os.path.basename(path)

    if name == LOCK_FILE:
        return "lock"

    return "tfvars" if name.endswith(".tfvars") else "tf"


def end_of_line(text, i):
    found = text.find("\n", i)

    return len(text) if found < 0 else found + 1


def unescaped(raw):
    for pattern, replacement in ESCAPES:
        raw = raw.replace(pattern, replacement)

    return raw


def skip_blanks(text, i):
    while i < len(text):
        character = text[i]

        if character in " \t\r\n":
            i += 1
        elif character == "#" or text.startswith("//", i):
            i = end_of_line(text, i)
        elif text.startswith("/*", i):
            closed = text.find("*/", i + 2)
            if closed < 0:
                raise Unreadable("unterminated block comment")
            i = closed + 2
        else:
            return i

    return i


def skip_interpolation(text, i):
    depth = 1

    while i < len(text):
        character = text[i]

        if character == '"':
            _, i = read_string(text, i)
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1

    raise Unreadable("unterminated interpolation")


def read_string(text, i):
    i += 1
    collected = []
    interpolated = False

    while True:
        if i >= len(text):
            raise Unreadable("unterminated string")

        character = text[i]

        if character == "\\":
            if i + 1 >= len(text):
                raise Unreadable("unterminated string")
            collected.append(text[i:i + 2])
            i += 2
            continue
        if character == '"':
            return (None if interpolated else unescaped("".join(collected))), i + 1
        if character == "\n":
            raise Unreadable("unterminated string")
        if text.startswith("${", i) or text.startswith("%{", i):
            interpolated = True
            i = skip_interpolation(text, i + 2)
            continue

        collected.append(character)
        i += 1


def skip_heredoc(text, i):
    i += 2

    if i < len(text) and text[i] == "-":
        i += 1

    found = NAME.match(text, i)

    if not found:
        raise Unreadable("heredoc with no marker")

    marker = found.group(0)
    i = end_of_line(text, found.end())

    while i < len(text):
        line = text.find("\n", i)
        line = len(text) if line < 0 else line
        if text[i:line].strip() == marker:
            return min(line + 1, len(text))
        i = line + 1

    raise Unreadable("unterminated heredoc %s" % marker)


def scalar(raw):
    if raw == "true":
        return True
    if raw == "false":
        return False
    if NUMBER.match(raw):
        return float(raw) if "." in raw or "e" in raw.lower() else int(raw)

    return None


def read_name(text, i):
    found = NAME.match(text, i)

    if not found:
        raise Unreadable("expected a name at '%s'" % text[i:i + 12].strip())

    return found.group(0), found.end()


def parse_opaque(text, i):
    collected = []
    depth = 0

    while i < len(text):
        character = text[i]

        if character == '"':
            start = i
            _, i = read_string(text, start)
            collected.append(text[start:i])
            continue
        if character == "#" or text.startswith("//", i):
            i = end_of_line(text, i)
            if depth == 0:
                break
            continue
        if text.startswith("/*", i):
            closed = text.find("*/", i + 2)
            if closed < 0:
                raise Unreadable("unterminated block comment")
            i = closed + 2
            continue
        if text.startswith("<<", i):
            i = skip_heredoc(text, i)
            collected.append("heredoc")
            continue
        if character in "([{":
            depth += 1
        elif character in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and character in "\n,":
            break

        collected.append(character)
        i += 1

    return scalar("".join(collected).strip()), i


def skip_balanced(text, i):
    depth = 0

    while i < len(text):
        character = text[i]

        if character == '"':
            _, i = read_string(text, i)
            continue
        if character == "#" or text.startswith("//", i):
            i = end_of_line(text, i)
            continue
        if text.startswith("/*", i):
            closed = text.find("*/", i + 2)
            if closed < 0:
                raise Unreadable("unterminated block comment")
            i = closed + 2
            continue
        if text.startswith("<<", i):
            i = skip_heredoc(text, i)
            continue
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1

    raise Unreadable("unterminated expression")


def parse_list(text, i):
    i += 1
    items = []

    while True:
        i = skip_blanks(text, i)

        if i >= len(text):
            raise Unreadable("unterminated list")
        if text[i] == "]":
            return items, i + 1
        if text[i] == ",":
            i += 1
            continue

        value, i = parse_value(text, i)
        items.append(value)


def parse_object(text, i):
    opening = i
    i = skip_blanks(text, i + 1)

    if i < len(text) and NAME.match(text, i) and NAME.match(text, i).group(0) == "for":
        return None, skip_balanced(text, opening)

    entries = {}

    while True:
        i = skip_blanks(text, i)

        if i >= len(text):
            raise Unreadable("unterminated object")
        if text[i] == "}":
            return entries, i + 1
        if text[i] == ",":
            i += 1
            continue

        if text[i] == '"':
            key, i = read_string(text, i)
            key = key or ""
        else:
            key, i = read_name(text, i)

        i = skip_blanks(text, i)

        if i >= len(text) or text[i] not in "=:":
            raise Unreadable("object key '%s' has no value" % key)

        value, i = parse_value(text, i + 1)
        entries[key] = value


def parse_value(text, i):
    i = skip_blanks(text, i)

    if i >= len(text):
        raise Unreadable("a value was expected")

    character = text[i]

    if character == '"':
        return read_string(text, i)
    if character == "[":
        return parse_list(text, i)
    if character == "{":
        return parse_object(text, i)
    if text.startswith("<<", i):
        return None, skip_heredoc(text, i)

    return parse_opaque(text, i)


def parse_body(text, i, top=False):
    attributes = {}
    blocks = []

    while True:
        i = skip_blanks(text, i)

        if i >= len(text):
            if top:
                return {"attributes": attributes, "blocks": blocks}, i
            raise Unreadable("unterminated block")
        if text[i] == "}":
            if top:
                raise Unreadable("unexpected '}'")
            return {"attributes": attributes, "blocks": blocks}, i + 1
        if text[i] == ",":
            i += 1
            continue

        name, i = read_name(text, i)
        labels = []
        i = skip_blanks(text, i)

        while i < len(text) and text[i] == '"':
            label, i = read_string(text, i)
            labels.append(label)
            i = skip_blanks(text, i)

        if i < len(text) and text[i] == "=" and not text.startswith("==", i):
            if labels:
                raise Unreadable("'%s' carries labels and a value" % name)
            value, i = parse_value(text, i + 1)
            attributes[name] = value
        elif i < len(text) and text[i] == "{":
            body, i = parse_body(text, i + 1)
            blocks.append((name, labels, body))
        else:
            raise Unreadable("expected '=' or a block body after '%s'" % name)


def parse(text):
    body, _ = parse_body(text, 0, top=True)

    return body


def blocks_named(body, name):
    return [(labels, nested) for kind, labels, nested in body["blocks"] if kind == name]


def truncated(value):
    if isinstance(value, str) and len(value) > MAX_VALUE:
        return value[:MAX_VALUE]

    return value


def redacted(name, value):
    if any(hint in name.lower() for hint in SECRET_NAMES):
        return None
    if isinstance(value, bool) or isinstance(value, (int, float, str)):
        return truncated(value)

    return None


def declared_flag(attributes, flag, implied):
    if flag and isinstance(attributes.get(flag), bool):
        return attributes[flag]
    if any(name in attributes for name in implied):
        return True

    return None


def backend_of(bodies):
    for body in bodies:
        for _, settings in blocks_named(body, "terraform"):
            for labels, declared in blocks_named(settings, "backend"):
                kind = labels[0] if labels else "local"
                attributes = declared["attributes"]

                return {
                    "type": kind,
                    "attributes": dict(
                        (name, redacted(name, value)) for name, value in attributes.items()
                    ),
                    "encrypted": declared_flag(attributes, *ENCRYPTED_BY.get(kind, (None, ()))),
                    "locking": declared_flag(attributes, *LOCKED_BY.get(kind, (None, ()))),
                }

    return {"type": "local", "attributes": {}, "encrypted": None, "locking": None}


def pinned(constraint):
    if not constraint:
        return False

    parts = [part.strip() for part in constraint.split(",") if part.strip()]

    return len(parts) == 1 and bool(EXACT.match(parts[0]))


def requirement(name, declared):
    if isinstance(declared, str):
        return {"name": name, "source": None, "version": declared, "pinned": pinned(declared)}

    declared = declared if isinstance(declared, dict) else {}
    version = declared.get("version") if isinstance(declared.get("version"), str) else None

    return {
        "name": name,
        "source": declared.get("source") if isinstance(declared.get("source"), str) else None,
        "version": version,
        "pinned": pinned(version),
    }


def providers_of(bodies):
    found = []
    named = set()

    for body in bodies:
        for _, settings in blocks_named(body, "terraform"):
            declarations = dict(settings["attributes"].get("required_providers") or {})
            for _, required in blocks_named(settings, "required_providers"):
                declarations.update(required["attributes"])

            for name in sorted(declarations):
                if name not in named:
                    named.add(name)
                    found.append(requirement(name, declarations[name]))

    for body in bodies:
        for labels, _ in blocks_named(body, "provider"):
            name = labels[0] if labels else None
            if name and name not in named:
                named.add(name)
                found.append({"name": name, "source": None, "version": None, "pinned": False})

    return found


def module_kind(source):
    local = source.startswith("./") or source.startswith("../") or source.startswith("/")
    git = not local and (
        source.startswith(GIT_PREFIXES) or source.endswith(".git") or ".git//" in source
    )

    return local, (not local and not git and bool(REGISTRY.match(source))), git


def modules_of(bodies):
    found = []

    for body in bodies:
        for labels, declared in blocks_named(body, "module"):
            source = declared["attributes"].get("source")
            source = source if isinstance(source, str) else None
            version = declared["attributes"].get("version")
            local, registry, git = module_kind(source) if source else (False, False, False)

            found.append({
                "name": labels[0] if labels else None,
                "source": source,
                "version": version if isinstance(version, str) else None,
                "local": local,
                "registry": registry,
                "git": git,
            })

    return found


def resources_of(bodies):
    counted = {}

    for body in bodies:
        for labels, _ in blocks_named(body, "resource"):
            kind = labels[0] if labels else "unknown"
            counted[kind] = counted.get(kind, 0) + 1

    return counted


def variables_of(bodies):
    found = []

    for body in bodies:
        for labels, declared in blocks_named(body, "variable"):
            attributes = declared["attributes"]
            found.append({
                "name": labels[0] if labels else None,
                "sensitive": attributes.get("sensitive") is True,
                "hasDefault": "default" in attributes,
            })

    return found


def lockfile_of(path, body):
    if body is None:
        return {"present": False, "path": None, "providers": []}

    found = []

    for labels, declared in blocks_named(body, "provider"):
        address = labels[0] if labels else ""
        version = declared["attributes"].get("version")
        hashes = declared["attributes"].get("hashes")

        found.append({
            "name": address.rsplit("/", 1)[-1],
            "source": address,
            "version": version if isinstance(version, str) else None,
            "hashes": len(hashes) if isinstance(hashes, list) else 0,
        })

    return {"present": True, "path": path, "providers": found}


def var_files_of(files):
    return [
        {"path": path, "variables": sorted(body["attributes"])}
        for path, body in files
        if path.endswith(".tfvars")
    ]


def build_roots(parsed, unparsed):
    directories = set(directory_of(path) for path in parsed if path.endswith(".tf"))
    directories |= set(
        directory_of(entry["path"]) for entry in unparsed if entry["path"].endswith(".tf")
    )

    broken = {}
    for entry in unparsed:
        where = directory_of(entry["path"])
        broken[where] = broken.get(where, 0) + 1

    roots = []

    for where in sorted(directories):
        files = sorted((path, body) for path, body in parsed.items() if directory_of(path) == where)
        bodies = [body for path, body in files if path.endswith(".tf")]
        lock = dict(files).get(where + "/" + LOCK_FILE if where != "." else LOCK_FILE)
        counted = resources_of(bodies)

        roots.append({
            "path": where,
            "backend": backend_of(bodies),
            "providers": providers_of(bodies),
            "modules": modules_of(bodies),
            "resources": counted,
            "resourceTypes": sorted(counted),
            "variables": variables_of(bodies),
            "varFiles": var_files_of(files),
            "lockfile": lockfile_of(
                (where + "/" + LOCK_FILE if where != "." else LOCK_FILE) if lock else None, lock
            ),
            "unparsed": broken.get(where, 0),
        })

    return roots


def state_files(prefix):
    found = []

    for where, directories, names in os.walk("."):
        directories[:] = [it for it in directories if it not in SKIPPED]

        for name in names:
            if not name.endswith(STATE):
                continue

            path = slashed(os.path.relpath(os.path.join(where, name), "."))

            if not under(prefix, path):
                continue

            try:
                found.append({"path": path, "bytes": os.path.getsize(path)})
            except OSError:
                found.append({"path": path, "bytes": None})

    return sorted(found, key=lambda it: it["path"])


def version_of(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("version", "resolved", "selected"):
            if isinstance(value.get(key), str):
                return value[key]

    return None


def selections(payload):
    if not isinstance(payload, dict):
        return {}

    for key in ("provider_selections", "providers", "provider_versions"):
        found = payload.get(key)

        if not isinstance(found, dict):
            continue

        versions = dict(
            (name, version_of(value)) for name, value in found.items() if version_of(value)
        )

        if versions:
            return versions

    return {}


def payload_of(result):
    if result is None or result.returncode != 0:
        return None

    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def asked(tool, where):
    for arguments in (("providers", "-json"), ("version", "-json")):
        found = selections(payload_of(tool.run(*arguments, cwd=where, timeout=20)))

        if found:
            return found

    return {}


def enriched(collector, roots):
    tool = collector.tool("terraform")

    if tool is None:
        return []

    resolved = []

    for root in roots:
        if not os.path.isdir(os.path.join(root["path"], ".terraform", "providers")):
            continue

        for source, version in sorted(asked(tool, root["path"]).items()):
            resolved.append({
                "root": root["path"],
                "name": source.rsplit("/", 1)[-1],
                "source": source,
                "version": version,
            })

    return resolved


with Collector() as collector:
    configured = collector.input("directory", ".")
    collector.facts["directory"] = collector.path(configured)

    prefix = normalized(configured)
    read = []
    unparsed = []
    parsed = {}

    for found, when, text in collector.reports(*CONFIGURATION):
        path = slashed(found)

        if not under(prefix, path):
            continue

        try:
            parsed[path] = parse(text)
        except Unreadable as failure:
            unparsed.append({"path": path, "reason": str(failure)})
            continue

        read.append({"path": path, "modified": when, "format": format_of(path)})

    states = state_files(prefix)

    if not read and not unparsed and not states:
        collector.empty("no Terraform configuration under %s" % prefix)

    roots = build_roots(parsed, unparsed)

    collector.sourced("report", read)

    resolved = enriched(collector, roots)

    def located(path):
        return slashed(collector.path(path))

    for entry in read + unparsed + states:
        entry["path"] = located(entry["path"])

    for entry in resolved:
        entry["root"] = located(entry["root"])

    for root in roots:
        root["path"] = located(root["path"])
        for var_file in root["varFiles"]:
            var_file["path"] = located(var_file["path"])
        if root["lockfile"]["path"]:
            root["lockfile"]["path"] = located(root["lockfile"]["path"])

    collector.facts["roots"] = roots
    collector.facts["stateFiles"] = states
    collector.facts["unparsed"] = sorted(unparsed, key=lambda it: it["path"])

    if resolved:
        collector.facts["resolved"] = resolved
