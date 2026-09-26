#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

REGISTRY_PINNED = fixture("registry-pinned.tf")

REGISTRY_UNPINNED = fixture("registry-unpinned.tf")

GIT_SHA = fixture("git-sha.tf")

GIT_TAG = fixture("git-tag.tf")

GIT_BARE = fixture("git-bare.tf")

LOCAL = fixture("local.tf")


class TerraformModulesPinnedTest(GuardrailTestCase):
    SCRIPT = "modules-pinned.py"
    COLLECT = ["terraform"]

    def test_passes_a_registry_module_that_names_a_version(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": REGISTRY_PINNED})))

    def test_fails_a_registry_module_that_names_none(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"main.tf": REGISTRY_UNPINNED})), "names no version"
        )

        self.assertEqual(violation["evidence"], "vpc in .")

    def test_passes_a_git_module_pinned_to_a_sha(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": GIT_SHA})))

    def test_fails_a_git_module_pinned_to_a_tag(self):
        self.assert_violation(self.check(self.workspace(**{"main.tf": GIT_TAG})), "at ref v1.4.0")

    def test_accepts_a_movable_ref_when_it_is_told_to(self):
        directory = self.workspace(**{"main.tf": GIT_TAG})

        self.assert_passed(self.check(directory, allowMovableRefs="true"))

    def test_fails_a_git_module_with_no_ref(self):
        self.assert_violation(self.check(self.workspace(**{"main.tf": GIT_BARE})), "with no ref")

    def test_leaves_a_module_in_this_repository_alone(self):
        directory = self.workspace(**{"main.tf": LOCAL, "modules/vpc/main.tf": "variable \"cidr\" {}\n"})

        self.assert_passed(self.check(directory))

    def test_skips_a_repository_that_declares_no_module(self):
        self.assert_skipped(self.check(self.workspace(**{"main.tf": "resource \"aws_s3_bucket\" \"a\" {}\n"})), "no Terraform root declares a module")


if __name__ == "__main__":
    unittest.main()
