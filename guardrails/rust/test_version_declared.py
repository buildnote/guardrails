#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CRATE = fixture("version-declared-crate.toml")

WITHOUT_VERSION = fixture("without-version.toml")

LOCKFILE = "version = 3\n"


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["rust"]

    def crate(self, **files):
        return self.workspace(**dict({"Cargo.toml": CRATE, "Cargo.lock": LOCKFILE}, **files))

    def test_passes_a_crate_that_declares_a_rust_version(self):
        self.assert_passed(self.check(self.crate()))

    def test_passes_a_crate_that_pins_a_toolchain_file(self):
        directory = self.workspace(**{
            "Cargo.toml": WITHOUT_VERSION,
            "Cargo.lock": LOCKFILE,
            "rust-toolchain.toml": "[toolchain]\nchannel = \"1.77.2\"\n",
        })

        self.assert_passed(self.check(directory))

    def test_fails_a_crate_that_declares_none(self):
        directory = self.workspace(**{"Cargo.toml": WITHOUT_VERSION, "Cargo.lock": LOCKFILE})

        violation = self.assert_violation(self.check(directory), "No Rust version declared in Cargo.toml")

        self.assertEqual(violation["evidence"], "Cargo.toml")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"Cargo.toml": CRATE.replace("1.76", "1.65"), "Cargo.lock": LOCKFILE})

        violation = self.assert_violation(self.check(directory), "asks for Rust 1.65, older than the 1.70 expected")

        self.assertEqual(violation["evidence"], "Cargo.toml (Rust 1.65)")

    def test_fails_a_toolchain_that_names_a_moving_channel(self):
        directory = self.crate(**{"rust-toolchain": "stable\n"})

        violation = self.assert_violation(self.check(directory), "asks for the stable channel, which moves under")

        self.assertEqual(violation["evidence"], "rust-toolchain (Rust stable)")

    def test_fails_a_nightly_toolchain_however_it_is_dated(self):
        directory = self.crate(**{"rust-toolchain.toml": "[toolchain]\nchannel = \"nightly-2026-03-01\"\n"})

        self.assert_violation(self.check(directory), "asks for the nightly-2026-03-01 channel, which moves under")

    def test_honours_the_floor_it_is_given(self):
        directory = self.crate()

        self.assert_passed(self.check(directory, minVersion="1.76"))
        self.assert_violation(self.check(directory, minVersion="1.78"), "older than the 1.78 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.crate(**{"rust-toolchain.toml": "[toolchain]\nchannel = \"1.77\"\n"})

        self.assert_passed(self.check(directory, minVersion="1.77.0"))
        self.assert_violation(self.check(directory, minVersion="1.77.1"), "older than the 1.77.1 expected")

    def test_skips_a_directory_with_no_cargo_build(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Cargo build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.crate(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "engine/Cargo.toml": CRATE,
            "engine/Cargo.lock": LOCKFILE,
        })

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
