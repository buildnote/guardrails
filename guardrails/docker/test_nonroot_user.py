#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

NON_ROOT = fixture("non-root.Dockerfile")

NO_USER = fixture("no-user.Dockerfile")

ROOT = fixture("root.Dockerfile")

UID_ZERO = fixture("uid-zero.Dockerfile")

ROOT_GROUP = fixture("root-group.Dockerfile")

NUMBERED = fixture("numbered.Dockerfile")

DROPS_ROOT = fixture("drops-root.Dockerfile")

INTERPOLATED = fixture("nonroot-user-interpolated.Dockerfile")


class DockerfileNonRootUserTest(GuardrailTestCase):
    SCRIPT = "nonroot-user.py"
    COLLECT = ["docker"]

    def dockerfile(self, text, name="Dockerfile"):
        return self.workspace(**{name: text})

    def test_passes_a_dockerfile_that_ends_on_an_unprivileged_user(self):
        self.assert_passed(self.check(self.dockerfile(NON_ROOT)))

    def test_passes_a_dockerfile_that_ends_on_a_numeric_user(self):
        self.assert_passed(self.check(self.dockerfile(NUMBERED)))

    def test_passes_a_dockerfile_that_drops_root_before_the_entrypoint(self):
        self.assert_passed(self.check(self.dockerfile(DROPS_ROOT)))

    def test_fails_a_dockerfile_that_declares_no_user(self):
        violation = self.assert_violation(
            self.check(self.dockerfile(NO_USER)),
            "The Dockerfile Dockerfile declares no USER, so everything the image runs, runs as root.",
        )

        self.assertEqual(violation["evidence"], "Dockerfile")

    def test_fails_a_dockerfile_that_ends_on_root(self):
        violation = self.assert_violation(
            self.check(self.dockerfile(ROOT)),
            "The Dockerfile Dockerfile ends on USER root, so the container runs its process as uid 0.",
        )

        self.assertEqual(violation["evidence"], "Dockerfile USER root")

    def test_fails_a_dockerfile_that_ends_on_uid_zero(self):
        self.assert_violation(
            self.check(self.dockerfile(UID_ZERO)),
            "ends on USER 0:0",
        )

    def test_fails_a_dockerfile_that_ends_on_the_root_group(self):
        self.assert_violation(
            self.check(self.dockerfile(ROOT_GROUP)),
            "ends on USER root:root",
        )

    def test_passes_a_user_the_collected_names_cannot_resolve(self):
        result = self.check(self.dockerfile(INTERPOLATED))

        self.assert_passed(result)
        self.assertIn("cannot resolve", result.output)

    def test_reports_every_dockerfile_in_the_tree(self):
        workspace = self.workspace(**{
            "Dockerfile": NO_USER,
            "services/api/Dockerfile": ROOT,
        })

        result = self.check(workspace)

        self.assertEqual(len(result.violations), 2)
        self.assertIn("The Dockerfile services/api/Dockerfile ends on USER root", result.messages[1])

    def test_skips_a_repository_with_no_dockerfile(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no Dockerfile matched",
        )


if __name__ == "__main__":
    unittest.main()
