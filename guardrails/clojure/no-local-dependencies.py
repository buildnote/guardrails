#!/usr/bin/env python3
from guardrail import Guardrail

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
    local = [it for it in direct if it["origin"] == "local"]

    for dependency in local:
        guardrail.violation(
            "%s (%s)" % (dependency["name"], dependency["source"]),
            "%s takes %s from a :local/root, so the build compiles a directory outside the checkout and this commit "
            "does not say what went into it" % (dependency["source"], dependency["name"]),
        )

    if not local:
        guardrail.log(
            "none of the %d dependencies read from %s comes from a local root"
            % (len(direct), ", ".join(clojure["sources"]))
        )

    if clojure["scanned"]:
        guardrail.log(
            "%s is Clojure read by pattern, so a dependency it adds inside a function or a reader conditional is "
            "not among the %d read" % (", ".join(clojure["scanned"]), len(direct))
        )
