#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

REMOTE = fixture("remote-backend.tf")

NO_BACKEND = fixture("pinned.tf")

LOCAL_BACKEND = fixture("local-backend.tf")

CALLS_MODULE = REMOTE + fixture("remote-state-module-call.tf")

MODULE = fixture("remote-state-module.tf")

BROKEN = fixture("broken.tf")

STATE = """{"version": 4, "serial": 3, "lineage": "8f2c", "resources": []}"""


class TerraformRemoteStateTest(GuardrailTestCase):
    SCRIPT = "remote-state.py"
    COLLECT = ["terraform"]

    def test_passes_a_root_that_stores_its_state_remotely(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": REMOTE})))

    def test_fails_a_root_that_declares_no_backend(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"main.tf": NO_BACKEND})),
            "The Terraform root . declares no remote backend, so its state is written to a local file",
        )

        self.assertEqual(violation["evidence"], ".")

    def test_fails_a_root_that_declares_the_local_backend(self):
        self.assert_violation(
            self.check(self.workspace(**{"infra/main.tf": LOCAL_BACKEND})),
            "The Terraform root infra declares no remote backend",
        )

    def test_fails_a_state_file_left_in_the_tree(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"main.tf": REMOTE, "terraform.tfstate": STATE})),
            "The Terraform state file terraform.tfstate is present in the working tree, and state records "
            "every attribute of every resource, the sensitive ones included.",
        )

        self.assertEqual(violation["evidence"], "terraform.tfstate")

    def test_reports_the_backend_and_the_state_file_separately(self):
        result = self.check(self.workspace(**{"main.tf": NO_BACKEND, "terraform.tfstate": STATE}))

        self.assertEqual([violation["evidence"] for violation in result.violations], [".", "terraform.tfstate"])

    def test_leaves_the_state_file_alone_when_it_is_told_to(self):
        workspace = self.workspace(**{"main.tf": REMOTE, "terraform.tfstate": STATE})

        self.assertEqual(self.check(workspace).code, 1)
        self.assert_passed(self.check(workspace, checkStateFiles="false"))

    def test_passes_a_reusable_module_another_root_takes_on(self):
        workspace = self.workspace(**{
            "main.tf": CALLS_MODULE,
            "modules/network/main.tf": MODULE,
        })

        result = self.check(workspace)

        self.assert_passed(result)
        self.assertIn("modules/network is a reusable module", result.output)

    def test_passes_a_module_directory_nobody_calls(self):
        self.assert_passed(self.check(self.workspace(**{
            "main.tf": REMOTE,
            "modules/network/main.tf": MODULE,
        })))

    def test_judges_a_module_directory_the_globs_do_not_name(self):
        self.assert_violation(
            self.check(
                self.workspace(**{"main.tf": REMOTE, "modules/network/main.tf": MODULE}),
                modulePaths="shared/*",
            ),
            "The Terraform root modules/network declares no remote backend",
        )

    def test_passes_a_root_it_could_only_read_in_part(self):
        result = self.check(self.workspace(**{"main.tf": NO_BACKEND, "broken.tf": BROKEN}))

        self.assert_passed(result)
        self.assertIn("was read from part of its configuration", result.output)

    def test_skips_a_repository_with_no_terraform(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no Terraform configuration under .",
        )


if __name__ == "__main__":
    unittest.main()
