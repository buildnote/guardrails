#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

LOCK_FILE = ".terraform.lock.hcl"

PINNED = fixture("pinned.tf")

RANGED = fixture("ranged.tf")

UNCONSTRAINED = fixture("unconstrained.tf")

NO_PROVIDERS = fixture("no-providers.tf")

CALLS_MODULE = PINNED + fixture("no-plaintext-secrets-module-call.tf")

MODULE = fixture("providers-pinned-module.tf")

BROKEN = fixture("broken.tf")

LOCK = fixture("lock.hcl")


class TerraformProvidersPinnedTest(GuardrailTestCase):
    SCRIPT = "providers-pinned.py"
    COLLECT = ["terraform"]

    def test_passes_a_root_that_pins_every_provider_and_commits_the_lock(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": PINNED, LOCK_FILE: LOCK})))

    def test_fails_a_provider_constrained_to_a_range(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"main.tf": RANGED, LOCK_FILE: LOCK})),
            "The Terraform root . requires the provider aws and constrains it to ~> 6.0 rather than to one "
            "exact version, so two runs of this commit can resolve different versions.",
        )

        self.assertEqual(violation["evidence"], ". provider aws")

    def test_fails_a_provider_with_no_constraint_at_all(self):
        self.assert_violation(
            self.check(self.workspace(**{"main.tf": UNCONSTRAINED, LOCK_FILE: LOCK})),
            "requires the provider vault and declares no version constraint at all",
        )

    def test_fails_a_root_that_commits_no_lock_file(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"infra/main.tf": PINNED})),
            "The Terraform root infra commits no .terraform.lock.hcl, so the versions and the checksums of "
            "the providers it requires are resolved fresh on every runner.",
        )

        self.assertEqual(violation["evidence"], "infra/.terraform.lock.hcl")

    def test_asks_for_no_lock_file_when_it_is_told_not_to(self):
        workspace = self.workspace(**{"main.tf": PINNED})

        self.assertEqual(self.check(workspace).code, 1)
        self.assert_passed(self.check(workspace, requireLockfile="false"))

    def test_asks_for_no_lock_file_from_a_root_that_requires_no_provider(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": NO_PROVIDERS})))

    def test_passes_a_reusable_module_another_root_takes_on(self):
        result = self.check(self.workspace(**{
            "main.tf": CALLS_MODULE,
            LOCK_FILE: LOCK,
            "modules/network/main.tf": MODULE,
        }))

        self.assert_passed(result)
        self.assertIn("modules/network is a reusable module", result.output)

    def test_judges_a_module_directory_the_globs_do_not_name(self):
        result = self.check(
            self.workspace(**{"main.tf": PINNED, LOCK_FILE: LOCK, "modules/network/main.tf": MODULE}),
            modulePaths="shared/*",
        )

        self.assertEqual(result.code, 1)
        self.assertIn(
            "The Terraform root modules/network requires the provider aws and constrains it to ~> 6.0",
            result.messages[0],
        )

    def test_passes_a_root_it_could_only_read_in_part(self):
        result = self.check(self.workspace(**{
            "main.tf": PINNED,
            LOCK_FILE: LOCK,
            "infra/main.tf": RANGED,
            "infra/broken.tf": BROKEN,
        }))

        self.assert_passed(result)
        self.assertIn("infra was read from part of its configuration", result.output)

    def test_skips_a_repository_whose_only_roots_are_modules(self):
        self.assert_skipped(
            self.check(self.workspace(**{"modules/network/main.tf": MODULE})),
            "no live Terraform root was collected to judge",
        )

    def test_skips_a_repository_with_no_terraform(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no Terraform configuration under .",
        )


if __name__ == "__main__":
    unittest.main()
