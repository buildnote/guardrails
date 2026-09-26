#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

LOCKED = fixture("locked.tf")

DYNAMO = fixture("dynamo.tf")

UNLOCKED = fixture("plain.tf")

MODULE = fixture("state-encrypted-module.tf")


class TerraformStateLockingTest(GuardrailTestCase):
    SCRIPT = "state-locking.py"
    COLLECT = ["terraform"]

    def test_passes_a_backend_that_holds_the_lock_itself(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": LOCKED})))

    def test_passes_a_backend_that_locks_in_dynamodb(self):
        self.assert_passed(self.check(self.workspace(**{"main.tf": DYNAMO})))

    def test_fails_a_backend_that_declares_no_locking(self):
        violation = self.assert_violation(self.check(self.workspace(**{"main.tf": UNLOCKED})), "declares no locking")

        self.assertEqual(violation["evidence"], ".")

    def test_leaves_a_reusable_module_alone(self):
        directory = self.workspace(**{"main.tf": LOCKED, "modules/vpc/main.tf": MODULE})

        self.assert_passed(self.check(directory))

    def test_skips_a_repository_with_no_terraform(self):
        self.assert_skipped(self.check(self.workspace()), "no Terraform")


if __name__ == "__main__":
    unittest.main()
