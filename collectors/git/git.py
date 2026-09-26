#!/usr/bin/env python3
from guardrail import Collector

FIELD = "\x1f"
RECORD = "\x1e"
FORMAT = FIELD.join(["%H", "%P", "%an", "%ae", "%aI", "%cn", "%ce", "%cI", "%s", "%B"]) + RECORD


def person(name, email, date):
    return {"name": name, "email": email, "date": date}


def commit_of(record):
    parts = record.split(FIELD)
    if len(parts) < 10:
        return None

    sha, parents, author, author_email, authored, committer, committer_email, committed, subject, message = parts[:10]
    parents = parents.split()
    message = message.rstrip("\n")

    return {
        "sha": sha,
        "short": sha[:7],
        "parents": parents,
        "merge": len(parents) > 1,
        "subject": subject,
        "message": message,
        "body": "\n".join(message.split("\n")[1:]).strip("\n"),
        "author": person(author, author_email, authored),
        "committer": person(committer, committer_email, committed),
    }


def lines(value):
    return int(value) if value.isdigit() else None


def changes_in(output):
    tokens = output.split("\0")
    changes = []
    index = 0

    while index < len(tokens):
        record = tokens[index]
        index += 1

        if not record:
            continue

        fields = record.split("\t", 2)
        if len(fields) < 3:
            continue

        added, deleted, path = fields

        if not path:
            path = tokens[index + 1] if index + 1 < len(tokens) else ""
            index += 2

        if not path:
            continue

        changes.append({
            "path": path,
            "added": lines(added),
            "deleted": lines(deleted),
            "binary": added == "-",
        })

    return changes


with Collector() as collector:
    base_ref = collector.input("baseRef", "origin/main")

    inside = collector.run("git", "rev-parse", "--git-dir")
    collector.facts["repository"] = inside is not None and inside.returncode == 0

    if not collector.facts["repository"]:
        collector.invalid("not a git repository")

    root = collector.run("git", "rev-parse", "--show-toplevel")
    collector.facts["root"] = root.stdout.strip() if root.returncode == 0 else None

    head = collector.run("git", "rev-parse", "HEAD")
    branch = collector.run("git", "rev-parse", "--abbrev-ref", "HEAD")
    tags = collector.run("git", "tag", "--points-at", "HEAD")
    sha = head.stdout.strip() if head.returncode == 0 else None
    named = branch.stdout.strip() if branch.returncode == 0 else ""

    collector.facts["head"] = {
        "sha": sha,
        "short": sha[:7] if sha else None,
        "branch": None if named in ("", "HEAD") else named,
        "detached": named == "HEAD",
        "tags": tags.stdout.split() if tags.returncode == 0 else [],
    }

    remotes = {}
    listed = collector.run("git", "remote", "-v")
    if listed.returncode == 0:
        for line in listed.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1]
    collector.facts["remotes"] = remotes

    status = collector.run("git", "status", "--porcelain")
    collector.facts["dirty"] = bool(status.stdout.strip()) if status.returncode == 0 else None

    collector.facts["baseRef"] = base_ref
    collector.facts["commits"] = []
    collector.facts["changedFiles"] = []
    collector.facts["changes"] = []

    base = collector.run("git", "rev-parse", "--verify", "--quiet", base_ref)
    collector.facts["resolved"] = base.returncode == 0

    if not collector.facts["resolved"]:
        collector.invalid("base ref %s is not resolvable" % base_ref)

    collector.facts["baseSha"] = base.stdout.strip()

    log = collector.run("git", "log", "--format=" + FORMAT, "%s..HEAD" % base_ref)
    if log.returncode != 0:
        collector.invalid(log.stderr.strip())

    for record in log.stdout.split(RECORD):
        record = record.strip("\n")
        if not record.strip():
            continue
        commit = commit_of(record)
        if commit:
            collector.facts["commits"].append(commit)

    changed = collector.run("git", "diff", "-z", "--name-only", "%s...HEAD" % base_ref)
    if changed.returncode == 0:
        collector.facts["changedFiles"] = [path for path in changed.stdout.split("\0") if path]

    counted = collector.run("git", "diff", "-z", "--numstat", "%s...HEAD" % base_ref)
    if counted.returncode == 0:
        collector.facts["changes"] = changes_in(counted.stdout)
