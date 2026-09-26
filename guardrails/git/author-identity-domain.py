#!/usr/bin/env python3
from guardrail import Guardrail

BOT_SUFFIX = "[bot]@users.noreply.github.com"


def domain_of(address):
    return address.rpartition("@")[2].lower()


def named(roles):
    return " and ".join(roles) if len(roles) < 3 else ", ".join(roles)


with Guardrail() as guardrail:
    git = guardrail.facts("git", "no git repository")
    configured = [it.strip().lower().lstrip("@") for it in guardrail.input("domains", "").split(",") if it.strip()]
    allow_bots = guardrail.input("allowBots", "true").strip().lower() != "false"

    if not git["resolved"]:
        guardrail.skip("base ref %s is not resolvable" % git["baseRef"])

    if git["commits"] and not configured:
        guardrail.skip("no domains are configured, so no address can be judged")

    for commit in git["commits"]:
        unknown = {}

        for role in ("author", "committer"):
            address = commit[role]["email"]

            if allow_bots and address.endswith(BOT_SUFFIX):
                continue

            if domain_of(address) in configured:
                continue

            unknown.setdefault(address, []).append(role)

        for address, roles in sorted(unknown.items()):
            guardrail.violation(
                "%s %s <%s>" % (commit["short"], named(roles), address),
                "Commit %s names its %s as <%s>, which is not on %s" % (
                    commit["short"], named(roles), address, ", ".join(configured)
                )
            )
