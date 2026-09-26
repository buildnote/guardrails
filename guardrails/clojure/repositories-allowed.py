#!/usr/bin/env python3
from urllib.parse import urlparse

from guardrail import Guardrail

DEFAULT_HOSTS = "repo1.maven.org,repo.clojars.org,clojars.org,central.sonatype.com"


def host_of(repository):
    return (urlparse(repository["url"] or "").hostname or "").lower()


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    allowed = [it.strip().lower() for it in guardrail.input("allowedHosts", DEFAULT_HOSTS).split(",") if it.strip()]
    clojure = guardrail.facts("clojure", "no Clojure build in %s" % project_dir)

    if clojure.get("incomplete"):
        guardrail.skip(clojure["incomplete"])

    if not clojure["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if not clojure["sources"]:
        guardrail.skip("no manifest in %s could be read as a Clojure build" % project_dir)

    if not allowed:
        guardrail.skip("no repository host was named as one the team allows")

    data = [it for it in clojure["sources"] if it not in clojure["scanned"]]

    if not data:
        guardrail.skip(
            "%s is Clojure read by pattern, so the repositories it adds are not among what was read"
            % ", ".join(clojure["scanned"])
        )

    if clojure["scanned"]:
        guardrail.log(
            "%s is Clojure read by pattern, so a repository it adds is not among what was read"
            % ", ".join(clojure["scanned"])
        )

    repositories = clojure["repositories"]
    refused = [it for it in repositories if host_of(it) not in allowed]

    for repository in refused:
        host = host_of(repository)

        if not host:
            guardrail.violation(
                "%s (%s)" % (repository["name"], ", ".join(data)),
                "The repository %s in %s names no host to resolve from, so nothing says where the artifacts it "
                "serves come from" % (repository["name"], ", ".join(data)),
            )
        else:
            guardrail.violation(
                "%s (%s)" % (repository["name"], host),
                "The repository %s resolves from %s, which is not a host the team allows, and a repository nobody "
                "vetted is what a dependency confusion attack needs" % (repository["name"], host),
            )

    if repositories and not refused:
        guardrail.log("resolves from %s" % ", ".join(sorted(set(host_of(it) for it in repositories))))
