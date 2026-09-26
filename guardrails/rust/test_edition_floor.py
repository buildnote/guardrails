#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CRATE = fixture("edition-floor-crate.toml")

WITHOUT_EDITION = fixture("without-edition.toml")

WORKSPACE = fixture("workspace.toml")

MEMBER = fixture("edition-floor-member.toml")

LOCKFILE = "version = 3\n"


class EditionFloorTest(GuardrailTestCase):
    SCRIPT = "edition-floor.py"
    COLLECT = ["rust"]

    def crate(self, manifest=CRATE, **files):
        return self.workspace(**dict({"Cargo.toml": manifest, "Cargo.lock": LOCKFILE}, **files))

    def test_passes_a_crate_at_the_floor(self):
        self.assert_passed(self.check(self.crate()))

    def test_passes_a_crate_past_the_floor(self):
        self.assert_passed(self.check(self.crate(CRATE.replace("2021", "2024"))))

    def test_fails_a_crate_older_than_the_floor(self):
        violation = self.assert_violation(
            self.check(self.crate(CRATE.replace("2021", "2015"))),
            "The Cargo build in . declares the 2015 edition, older than the 2021 expected",
        )

        self.assertEqual(violation["evidence"], "Cargo.toml (edition 2015)")

    def test_fails_a_crate_that_declares_none(self):
        violation = self.assert_violation(
            self.check(self.crate(WITHOUT_EDITION)), "No Rust edition is declared in Cargo.toml"
        )

        self.assertEqual(violation["evidence"], "Cargo.toml")

    def test_reads_the_edition_a_workspace_member_declares(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "Cargo.lock": LOCKFILE,
            "crates/core/Cargo.toml": MEMBER,
        })

        violation = self.assert_violation(
            self.check(directory), "declares the 2018 edition, older than the 2021 expected"
        )

        self.assertEqual(violation["evidence"], "Cargo.toml, crates/core/Cargo.toml (edition 2018)")

    def test_skips_a_workspace_whose_members_were_left_out_of_the_facts(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "Cargo.lock": LOCKFILE,
            "crates/core/Cargo.toml": MEMBER,
        })

        self.assert_skipped(self.check(directory, maxMembers="0"), "1 workspace members were left out")

    def test_still_fails_what_it_did_read_when_members_were_left_out(self):
        directory = self.workspace(**{
            "Cargo.toml": CRATE.replace("2021", "2015") + "\n[workspace]\nmembers = [\"crates/*\"]\n",
            "Cargo.lock": LOCKFILE,
            "crates/core/Cargo.toml": MEMBER,
        })

        self.assert_violation(self.check(directory, maxMembers="0"), "declares the 2015 edition")

    def test_honours_the_floor_it_is_given(self):
        directory = self.crate(CRATE.replace("2021", "2018"))

        self.assert_passed(self.check(directory, minEdition="2018"))
        self.assert_violation(self.check(directory, minEdition="2021"), "older than the 2021 expected")

    def test_skips_a_floor_that_is_not_an_edition_year(self):
        result = self.check(self.crate(), minEdition="twenty-one")

        self.assert_skipped(result, "minEdition 'twenty-one' is not a number")

    def test_skips_a_directory_with_no_cargo_build(self):
        self.assert_skipped(self.check(self.workspace(**{"pom.xml": "<project/>\n"})), "no Cargo build in .")

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
