#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CRATE = fixture("no-git-dependencies-crate.toml")

FROM_GIT = fixture("from-git.toml")

WORKSPACE = fixture("workspace.toml")

WORKSPACE_FROM_GIT = fixture("workspace-from-git.toml")

MEMBER = fixture("no-git-dependencies-member.toml")

ROOT_FROM_GIT = fixture("root-from-git.toml")

MEMBER_FROM_GIT = fixture("member-from-git.toml")

LOCKFILE = "version = 3\n"


class NoGitDependenciesTest(GuardrailTestCase):
    SCRIPT = "no-git-dependencies.py"
    COLLECT = ["rust"]

    def crate(self, manifest=CRATE, **files):
        return self.workspace(**dict({"Cargo.toml": manifest, "Cargo.lock": LOCKFILE}, **files))

    def members(self, member):
        return self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "Cargo.lock": LOCKFILE,
            "crates/core/Cargo.toml": member,
        })

    def test_passes_a_crate_that_depends_on_a_registry_and_a_path(self):
        self.assert_passed(self.check(self.crate()))

    def test_passes_a_workspace_whose_members_inherit_their_versions(self):
        self.assert_passed(self.check(self.members(MEMBER)))

    def test_fails_a_crate_that_fetches_a_dependency_from_a_url(self):
        directory = self.crate(FROM_GIT.replace(
            "proptest = { git = \"https://github.com/proptest-rs/proptest\" }", "proptest = \"1.4.0\""
        ))

        violation = self.assert_violation(self.check(directory), "declares tracing as a git dependency")

        self.assertEqual(violation["evidence"], "tracing in Cargo.toml")

    def test_fails_every_scope_a_git_dependency_is_declared_in(self):
        result = self.check(self.crate(FROM_GIT))

        self.assertEqual(
            [it["evidence"] for it in result.violations],
            ["tracing in Cargo.toml", "proptest in Cargo.toml"],
        )
        self.assertEqual(result.code, 1)

    def test_fails_a_workspace_that_declares_a_git_dependency_for_its_members(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE_FROM_GIT,
            "Cargo.lock": LOCKFILE,
            "crates/core/Cargo.toml": MEMBER,
        })

        violation = self.assert_violation(self.check(directory), "Cargo.toml declares tracing as a git dependency")

        self.assertEqual(violation["evidence"], "tracing in Cargo.toml")

    def test_names_the_member_manifest_that_fetches_from_a_url(self):
        violation = self.assert_violation(
            self.check(self.members(MEMBER_FROM_GIT)),
            "crates/core/Cargo.toml declares tracing as a git dependency",
        )

        self.assertEqual(violation["evidence"], "tracing in crates/core/Cargo.toml")

    def test_skips_a_workspace_whose_members_were_left_out_of_the_facts(self):
        self.assert_skipped(self.check(self.members(MEMBER), maxMembers="0"), "1 workspace members were left out")

    def test_still_fails_what_it_did_read_when_members_were_left_out(self):
        directory = self.workspace(**{
            "Cargo.toml": ROOT_FROM_GIT,
            "Cargo.lock": LOCKFILE,
            "crates/core/Cargo.toml": MEMBER,
        })

        self.assert_violation(self.check(directory, maxMembers="0"), "declares tracing as a git dependency")

    def test_skips_a_directory_with_no_cargo_build(self):
        self.assert_skipped(self.check(self.workspace(**{"go.mod": "module widget\n"})), "no Cargo build in .")

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
