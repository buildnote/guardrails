#!/usr/bin/env python3
from guardrail import Guardrail


def why(dependency):
    if dependency["origin"] == "git":
        return "names no :git/sha, so a build resolves whatever that branch has moved to by the time it runs"
    if dependency["origin"] == "local":
        return "comes from a :local/root, so what it resolves to is whatever that directory holds when the build runs"
    if dependency["version"]:
        return (
            "asks for %s rather than one released version, so two builds of this commit can compile different code"
            % dependency["version"]
        )

    return "names no version, so two builds of this commit can compile different code"


with Guardrail() as guardrail:
    project_dir = guardrail.input("projectDir", ".")
    clojure = guardrail.facts("clojure", "no Clojure build in %s" % project_dir)

    if clojure.get("incomplete"):
        guardrail.skip(clojure["incomplete"])

    if not clojure["exists"]:
        guardrail.skip("%s is not a directory" % project_dir)

    if not clojure["sources"]:
        guardrail.skip("no manifest in %s could be read as a Clojure build" % project_dir)

    direct = clojure["dependencies"]["direct"]
    moving = [it for it in direct if not it["pinned"]]

    for dependency in moving:
        guardrail.violation(
            "%s (%s)" % (dependency["name"], dependency["source"]),
            "The dependency %s in %s %s" % (dependency["name"], dependency["source"], why(dependency)),
        )

    if not moving:
        guardrail.log("all %d dependencies read from %s are pinned" % (len(direct), ", ".join(clojure["sources"])))

    if clojure["scanned"]:
        guardrail.log(
            "%s is Clojure read by pattern, so a dependency it adds inside a function or a reader conditional is "
            "not among the %d read" % (", ".join(clojure["scanned"]), len(direct))
        )
