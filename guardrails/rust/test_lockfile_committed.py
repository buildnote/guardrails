#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CRATE = fixture("lockfile-committed-crate.toml")

LOCKFILE = fixture("lockfile.toml")


class LockfileCommittedTest(GuardrailTestCase):
    SCRIPT = "lockfile-committed.py"
    COLLECT = ["rust"]

    def test_passes_a_crate_that_commits_a_lock_file(self):
        directory = self.workspace(**{"Cargo.toml": CRATE, "Cargo.lock": LOCKFILE})

        self.assert_passed(self.check(directory))

    def test_fails_a_crate_that_commits_none(self):
        directory = self.workspace(**{"Cargo.toml": CRATE})

        violation = self.assert_violation(self.check(directory), "commits no lock file")

        self.assertEqual(violation["evidence"], "Cargo.toml")

    def test_skips_a_directory_with_no_cargo_build(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": "module widget\n"})), "no Cargo build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"Cargo.toml": CRATE, "Cargo.lock": LOCKFILE})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "engine/Cargo.toml": CRATE,
            "engine/Cargo.lock": LOCKFILE,
        })

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
