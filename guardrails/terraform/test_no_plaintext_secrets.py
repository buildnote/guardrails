#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

INNOCUOUS = fixture("innocuous.tf")

SENSITIVE = fixture("sensitive.tf")

PLAINTEXT = fixture("plaintext.tf")

SEVERAL = fixture("several.tf")

MODULE = fixture("no-plaintext-secrets-module.tf")

CALLS_MODULE = fixture("no-plaintext-secrets-module-call.tf")

BROKEN = fixture("broken.tf")


class TerraformNoPlaintextSecretsTest(GuardrailTestCase):
    SCRIPT = "no-plaintext-secrets.py"
    COLLECT = ["terraform"]

    def test_passes_variables_that_hold_no_credential(self):
        self.assert_passed(self.check(self.workspace(**{"variables.tf": INNOCUOUS})))

    def test_passes_a_credential_variable_marked_sensitive(self):
        self.assert_passed(self.check(self.workspace(**{"variables.tf": SENSITIVE})))

    def test_fails_a_credential_variable_that_is_not_marked_sensitive(self):
        violation = self.assert_violation(
            self.check(self.workspace(**{"variables.tf": PLAINTEXT})),
            "The Terraform root . declares the variable db_password, whose name matches *PASSWORD*, without "
            "sensitive = true, so its value is printed in every plan that reads it.",
        )

        self.assertEqual(violation["evidence"], ".:db_password")

    def test_names_the_root_it_read(self):
        self.assert_violation(
            self.check(self.workspace(**{"infra/variables.tf": PLAINTEXT})),
            "The Terraform root infra declares the variable db_password",
        )

    def test_reports_every_variable_it_finds(self):
        result = self.check(self.workspace(**{"variables.tf": SEVERAL}))

        self.assertEqual(
            [violation["evidence"] for violation in result.violations],
            [".:db_password", ".:signing_key"],
        )

    def test_judges_a_reusable_module_as_well_as_a_live_root(self):
        self.assert_violation(
            self.check(self.workspace(**{
                "main.tf": CALLS_MODULE,
                "modules/network/main.tf": MODULE,
            })),
            "The Terraform root modules/network declares the variable vault_token",
        )

    def test_judges_a_root_it_could_only_read_in_part(self):
        self.assert_violation(
            self.check(self.workspace(**{"variables.tf": PLAINTEXT, "broken.tf": BROKEN})),
            "The Terraform root . declares the variable db_password",
        )

    def test_judges_only_the_patterns_it_is_given(self):
        workspace = self.workspace(**{"variables.tf": PLAINTEXT})

        self.assertEqual(self.check(workspace).code, 1)
        self.assert_passed(self.check(workspace, patterns="*TOKEN*"))

    def test_reads_a_name_without_regard_to_case(self):
        self.assert_violation(
            self.check(self.workspace(**{"variables.tf": PLAINTEXT}), patterns="*password*"),
            "whose name matches *PASSWORD*",
        )

    def test_skips_when_no_pattern_is_configured(self):
        self.assert_skipped(
            self.check(self.workspace(**{"variables.tf": PLAINTEXT}), patterns=" , "),
            "no patterns are configured",
        )

    def test_skips_a_repository_with_no_terraform(self):
        self.assert_skipped(
            self.check(self.workspace(**{"README.md": "widget\n"})),
            "no Terraform configuration under .",
        )

    def test_skips_a_tree_holding_state_but_no_configuration(self):
        self.assert_skipped(
            self.check(self.workspace(**{"terraform.tfstate": '{"version": 4}'})),
            "no Terraform root was collected to judge",
        )


if __name__ == "__main__":
    unittest.main()
