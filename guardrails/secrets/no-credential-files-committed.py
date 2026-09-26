#!/usr/bin/env python3
from guardrail import Guardrail

PATTERN = ("*", "?", "[")

DEFAULT_PATHS = (
    ".env,.env.local,.env.development,.env.production,.env.test,"
    "id_rsa,id_dsa,id_ecdsa,id_ed25519,"
    ".npmrc,.netrc,kubeconfig,.kube/config,.aws/credentials,"
    "keystore.jks,keystore.p12,release.keystore"
)


def sized(described):
    return "unreadable" if "unreadable" in described else "%d bytes" % described.get("bytes", 0)


with Guardrail() as guardrail:
    configured = [path.strip() for path in guardrail.input("paths", DEFAULT_PATHS).split(",") if path.strip()]
    patterns = [path for path in configured if any(character in path for character in PATTERN)]

    if patterns:
        guardrail.skip(
            "%s is a pattern, and this guardrail reads exact paths: name the paths themselves"
            % ", ".join(patterns)
        )

    files = guardrail.facts("files")["files"]

    for path in configured:
        described = files.get(path)

        if described is None:
            guardrail.skip("%s was not collected" % path)

        if not described["present"]:
            continue

        guardrail.violation(
            "%s (%s)" % (path, sized(described)),
            "Credential file %s is in the checkout. Take it out of the repository, rotate whatever it carried "
            "and ignore the path." % path
        )
