#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

DIGEST = "sha256:4f2b3c1e9a0d5c7b8e6f1a2d3c4b5a69788899aabbccddeeff00112233445566"

MULTI_STAGE = fixture("multi-stage.Dockerfile") % DIGEST

BARE = """FROM ubuntu
RUN apt-get update
"""

TAGGED = """FROM ubuntu:latest
RUN apt-get update
"""

PINNED = """FROM ghcr.io/company/base:1.4.0@%s
RUN echo pinned
""" % DIGEST

SECRETS = fixture("secrets.Dockerfile")

BROKEN = fixture("broken.Dockerfile")

HADOLINT = fixture("hadolint.sarif")


CLEAN = fixture("hadolint-clean.sarif")


class DockerTest(CollectorTestCase):
    COLLECTOR = "docker"

    def pinning(self):
        return self.workspace(**{
            "Dockerfile": BARE,
            "Dockerfile.latest": TAGGED,
            "service/Dockerfile.release": PINNED,
        })

    def test_names_every_stage_of_a_multi_stage_build(self):
        facts = self.collect(self.workspace(Dockerfile=MULTI_STAGE))
        stages = facts["dockerfiles"][0]["stages"]

        self.assertEqual(facts["dockerfiles"][0]["path"], "Dockerfile")
        self.assertEqual([stage["name"] for stage in stages], ["build", "runtime"])
        self.assertEqual(stages[0]["image"], "golang:1.22")
        self.assertEqual(stages[0]["repository"], "golang")
        self.assertEqual(stages[0]["tag"], "1.22")
        self.assertIsNone(stages[0]["registry"])
        self.assertIsNone(stages[0]["digest"])
        self.assertEqual(stages[0]["platform"], "linux/amd64")
        self.assertIsNone(stages[1]["platform"])

    def test_reads_the_registry_and_the_digest_a_stage_pins(self):
        facts = self.collect(self.workspace(Dockerfile=MULTI_STAGE))
        runtime = facts["dockerfiles"][0]["stages"][1]

        self.assertEqual(runtime["registry"], "gcr.io")
        self.assertEqual(runtime["repository"], "distroless/static-debian12")
        self.assertEqual(runtime["digest"], DIGEST)
        self.assertIsNone(runtime["tag"])

    def test_reads_a_tag_and_a_digest_pinned_beside_each_other(self):
        facts = self.collect(self.pinning())
        pinned = self.dockerfile(facts, "service/Dockerfile.release")["stages"][0]

        self.assertEqual(pinned["registry"], "ghcr.io")
        self.assertEqual(pinned["repository"], "company/base")
        self.assertEqual(pinned["tag"], "1.4.0")
        self.assertEqual(pinned["digest"], DIGEST)

    def test_leaves_the_tag_null_when_the_from_names_none(self):
        facts = self.collect(self.pinning())

        self.assertIsNone(self.dockerfile(facts, "Dockerfile")["stages"][0]["tag"])
        self.assertEqual(self.dockerfile(facts, "Dockerfile.latest")["stages"][0]["tag"], "latest")

    def test_describes_every_dockerfile_it_finds(self):
        facts = self.collect(self.pinning())

        self.assertEqual(
            [dockerfile["path"] for dockerfile in facts["dockerfiles"]],
            ["Dockerfile", "Dockerfile.latest", "service/Dockerfile.release"],
        )

    def test_reads_the_user_the_image_ends_as(self):
        facts = self.collect(self.workspace(Dockerfile=MULTI_STAGE))

        self.assertEqual(facts["dockerfiles"][0]["user"], "10001")

    def test_leaves_the_user_null_when_the_file_sets_none(self):
        facts = self.collect(self.workspace(Dockerfile=SECRETS))

        self.assertIsNone(facts["dockerfiles"][0]["user"])
        self.assertFalse(facts["dockerfiles"][0]["healthcheck"])

    def test_counts_the_instructions_and_reads_the_ports_and_the_copied_paths(self):
        described = self.collect(self.workspace(Dockerfile=MULTI_STAGE))["dockerfiles"][0]

        self.assertEqual(described["exposedPorts"], ["8080", "9090/udp"])
        self.assertTrue(described["healthcheck"])
        self.assertEqual(described["copiedPaths"], ["go.mod", "go.sum", "/out/widget"])
        self.assertEqual(described["instructions"]["FROM"], 2)
        self.assertEqual(described["instructions"]["COPY"], 2)
        self.assertEqual(described["instructions"]["RUN"], 1)

    def test_collects_argument_and_variable_names_without_their_values(self):
        facts = self.collect(self.workspace(Dockerfile=SECRETS))
        described = facts["dockerfiles"][0]

        self.assertEqual(described["buildArgs"], ["NPM_TOKEN"])
        self.assertEqual(described["envKeys"], ["DATABASE_URL", "API_KEY", "LEGACY_HOME"])
        self.assertNotIn("hunter2mostsecret", json.dumps(facts))

    def test_says_which_line_it_could_not_read(self):
        facts = self.collect(self.workspace(Dockerfile=BROKEN))
        described = facts["dockerfiles"][0]

        self.assertEqual(described["unparsed"], "line 2 could not be read as an instruction")
        self.assertEqual(described["user"], "widget")
        self.assertNotIn("this line is not an instruction", json.dumps(facts))

    def test_narrows_discovery_to_the_globs_it_is_given(self):
        workspace = self.workspace(**{"Dockerfile": BARE, "tools/build.Dockerfile": TAGGED})

        facts = self.collect(workspace, dockerfiles="*.Dockerfile")

        self.assertEqual([it["path"] for it in facts["dockerfiles"]], ["tools/build.Dockerfile"])

    def test_reads_the_findings_of_a_hadolint_report_beside_the_dockerfile(self):
        workspace = self.workspace(**{"Dockerfile": MULTI_STAGE, "hadolint.sarif": HADOLINT})

        facts = self.collect(workspace)

        self.assertEqual(facts["source"], "report")
        self.assertEqual(len(facts["dockerfiles"]), 1)
        self.assertEqual(facts["lint"]["total"], 2)
        self.assertEqual(facts["lint"]["dropped"], 0)
        self.assertEqual(facts["lint"]["findings"][0]["id"], "DL3008")
        self.assertEqual(facts["lint"]["findings"][0]["severity"], "medium")
        self.assertEqual(facts["lint"]["findings"][0]["message"], "Pin versions in apt get install.")
        self.assertEqual(facts["lint"]["findings"][0]["path"], "Dockerfile")
        self.assertEqual(facts["lint"]["findings"][0]["line"], 2)
        self.assertEqual(facts["lint"]["findings"][1]["severity"], "high")

    def test_names_the_report_and_the_linter_that_wrote_it(self):
        workspace = self.workspace(**{"Dockerfile": MULTI_STAGE, "hadolint.sarif": HADOLINT})

        report = self.collect(workspace)["reports"][0]

        self.assertEqual(report["path"], "hadolint.sarif")
        self.assertEqual(report["format"], "sarif")
        self.assertEqual(report["producer"]["name"], "Haskell Dockerfile Linter")
        self.assertEqual(report["producer"]["version"], "2.12.0")
        self.assertIsNotNone(report["modified"])

    def test_drops_findings_over_the_limit_but_keeps_the_total_whole(self):
        workspace = self.workspace(**{"Dockerfile": MULTI_STAGE, "hadolint.sarif": HADOLINT})

        facts = self.collect(workspace, maxFindings="1")

        self.assertEqual(len(facts["lint"]["findings"]), 1)
        self.assertEqual(facts["lint"]["total"], 2)
        self.assertEqual(facts["lint"]["dropped"], 1)

    def test_a_report_that_found_nothing_is_not_the_same_as_no_report(self):
        workspace = self.workspace(**{"Dockerfile": MULTI_STAGE, "hadolint.sarif": CLEAN})

        facts = self.collect(workspace)

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["lint"]["total"], 0)
        self.assertEqual(facts["lint"]["findings"], [])
        self.assertNotIn("reason", facts)

    def test_collects_the_dockerfiles_when_no_report_was_left_behind(self):
        facts = self.collect(self.workspace(Dockerfile=MULTI_STAGE))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no hadolint report matched", facts["reason"])
        self.assertEqual(facts["reports"], [])
        self.assertEqual(len(facts["dockerfiles"][0]["stages"]), 2)
        self.assertNotIn("lint", facts)

    def test_says_it_found_no_dockerfile_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "# Widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no Dockerfile matched", facts["reason"])
        self.assertEqual(facts["dockerfiles"], [])

    def dockerfile(self, facts, path):
        return next(it for it in facts["dockerfiles"] if it["path"] == path)


if __name__ == "__main__":
    unittest.main()
