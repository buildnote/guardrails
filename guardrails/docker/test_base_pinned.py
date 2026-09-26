#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

NODE = "sha256:" + "a" * 64

RUNTIME = "sha256:" + "b" * 64

PINNED = fixture("pinned.Dockerfile") % (NODE, RUNTIME)

TAGGED = fixture("tagged.Dockerfile")

LATEST = fixture("latest.Dockerfile")

UNTAGGED = fixture("untagged.Dockerfile")

REUSED = fixture("reused.Dockerfile") % NODE

SCRATCH = fixture("scratch.Dockerfile") % NODE

INTERPOLATED = fixture("base-pinned-interpolated.Dockerfile")

TWO_STAGES = fixture("two-stages.Dockerfile")


class DockerfileBasePinnedTest(GuardrailTestCase):
    SCRIPT = "base-pinned.py"
    COLLECT = ["docker"]

    def dockerfile(self, text, name="Dockerfile"):
        return self.workspace(**{name: text})

    def test_passes_a_dockerfile_pinning_every_stage_to_a_digest(self):
        self.assert_passed(self.check(self.dockerfile(PINNED)))

    def test_fails_a_stage_pinned_only_by_a_tag(self):
        self.assert_violation(
            self.check(self.dockerfile(TAGGED)),
            "The Dockerfile Dockerfile builds stage 1 from node:20-alpine, which pins no digest",
        )

    def test_locates_the_stage_it_failed(self):
        violation = self.assert_violation(self.check(self.dockerfile(TAGGED)), "pins no digest")

        self.assertEqual(violation["evidence"], "Dockerfile stage 1")

    def test_names_a_stage_by_the_name_it_was_given(self):
        result = self.check(self.dockerfile(TWO_STAGES))

        self.assertEqual(result.violations[0]["evidence"], "Dockerfile stage build")
        self.assertIn('builds stage "build" from node:20-alpine', result.violations[0]["message"])

    def test_reports_every_unpinned_stage(self):
        self.assertEqual(len(self.check(self.dockerfile(TWO_STAGES)).violations), 2)

    def test_accepts_a_tag_when_tags_are_allowed(self):
        self.assert_passed(self.check(self.dockerfile(TAGGED), allowTags="true"))

    def test_fails_latest_even_when_tags_are_allowed(self):
        self.assert_violation(
            self.check(self.dockerfile(LATEST), allowTags="true"),
            "from node:latest, which is pinned to latest",
        )

    def test_fails_an_image_with_no_tag_when_tags_are_allowed(self):
        self.assert_violation(
            self.check(self.dockerfile(UNTAGGED), allowTags="true"),
            "from node, which names no tag, so it resolves to latest",
        )

    def test_fails_a_registry_nobody_allowed(self):
        violation = self.assert_violation(
            self.check(self.dockerfile(PINNED), registries="docker.io"),
            "whose registry gcr.io is not one of docker.io",
        )

        self.assertEqual(violation["evidence"], "Dockerfile stage 2 registry")

    def test_locates_the_registry_and_the_pin_apart_on_one_stage(self):
        result = self.check(self.dockerfile(TAGGED), registries="ghcr.io")

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            ["Dockerfile stage 1 registry", "Dockerfile stage 1"],
        )

    def test_passes_an_image_from_an_allowed_registry(self):
        self.assert_passed(self.check(self.dockerfile(PINNED), registries="docker.io,gcr.io"))

    def test_reads_an_image_naming_no_registry_as_docker_hub(self):
        self.assert_violation(
            self.check(self.dockerfile(TAGGED), allowTags="true", registries="ghcr.io"),
            "whose registry docker.io is not one of ghcr.io",
        )

    def test_passes_a_stage_that_builds_on_an_earlier_stage(self):
        self.assert_passed(self.check(self.dockerfile(REUSED)))

    def test_passes_a_stage_that_builds_from_scratch(self):
        self.assert_passed(self.check(self.dockerfile(SCRATCH)))

    def test_passes_a_base_image_the_collected_names_cannot_resolve(self):
        result = self.check(self.dockerfile(INTERPOLATED))

        self.assert_passed(result)
        self.assertIn("cannot resolve", result.output)

    def test_reads_every_dockerfile_in_the_tree(self):
        workspace = self.workspace(**{
            "Dockerfile": PINNED,
            "services/api/Dockerfile": TAGGED,
        })

        self.assert_violation(
            self.check(workspace),
            "The Dockerfile services/api/Dockerfile builds stage 1 from node:20-alpine",
        )

    def test_skips_a_repository_with_no_dockerfile(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no Dockerfile matched",
        )


if __name__ == "__main__":
    unittest.main()
