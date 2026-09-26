#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

CRATE = fixture("crate.toml")

WORKSPACE = fixture("workspace.toml")

MEMBER = fixture("member.toml")


INHERITING_WORKSPACE = fixture("inheriting-workspace.toml")

INHERITING_MEMBER = fixture("inheriting-member.toml")


class RustTest(CollectorTestCase):
    COLLECTOR = "rust"

    def crate(self, **files):
        return self.workspace(**dict({"Cargo.toml": CRATE, "Cargo.lock": "version = 3\n"}, **files))

    def test_reads_the_package_and_what_it_asks_for(self):
        facts = self.collect(self.crate())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "Cargo.toml")
        self.assertEqual(facts["sources"], ["Cargo.toml"])
        self.assertEqual(facts["edition"], "2021")
        self.assertFalse(facts["workspace"])
        self.assertEqual(facts["declared"], {"version": "1.76", "source": "Cargo.toml", "pinned": True})
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "Cargo.toml", "name": "widget"}])

    def test_reads_only_an_equals_requirement_as_pinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.crate())["dependencies"]["direct"])

        self.assertTrue(by_name["clap"]["pinned"])
        self.assertFalse(by_name["serde"]["pinned"])
        self.assertFalse(by_name["anyhow"]["pinned"])

    def test_says_where_each_dependency_comes_from(self):
        by_name = dict((it["name"], it) for it in self.collect(self.crate())["dependencies"]["direct"])

        self.assertEqual(by_name["serde"]["origin"], "registry")
        self.assertEqual(by_name["queue"]["origin"], "path")
        self.assertEqual(by_name["tracing"]["origin"], "git")
        self.assertIsNone(by_name["queue"]["version"])

    def test_carries_every_scope_a_dependency_is_declared_in(self):
        by_name = dict((it["name"], it) for it in self.collect(self.crate())["dependencies"]["direct"])

        self.assertEqual(by_name["anyhow"]["scopes"], ["dependencies", "dev-dependencies"])
        self.assertEqual(by_name["proptest"]["scopes"], ["dev-dependencies"])
        self.assertEqual(by_name["cc"]["scopes"], ["build-dependencies"])
        self.assertEqual(by_name["cc"]["source"], "Cargo.toml")

    def test_reads_a_toolchain_file_over_the_crate_floor(self):
        facts = self.collect(self.crate(**{"rust-toolchain.toml": "[toolchain]\nchannel = \"1.77.2\"\n"}))

        self.assertEqual(facts["declared"], {"version": "1.77.2", "source": "rust-toolchain.toml", "pinned": True})

    def test_reads_a_moving_channel_as_unpinned(self):
        facts = self.collect(self.crate(**{"rust-toolchain": "stable\n"}))

        self.assertEqual(facts["declared"], {"version": "stable", "source": "rust-toolchain", "pinned": False})

    def test_reads_every_member_of_a_workspace(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "crates/core/Cargo.toml": MEMBER,
        })
        facts = self.collect(directory)

        self.assertTrue(facts["workspace"])
        self.assertEqual(facts["sources"], ["Cargo.toml", "crates/core/Cargo.toml"])
        self.assertEqual(
            facts["projects"], [{"path": "crates/core", "manifest": "crates/core/Cargo.toml", "name": "widget-core"}]
        )
        self.assertEqual(facts["edition"], "2018")

    def test_reads_what_the_workspace_declares_for_its_members(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "crates/core/Cargo.toml": MEMBER,
        })
        by_source = {}
        for it in self.collect(directory)["dependencies"]["direct"]:
            by_source.setdefault(it["source"], {})[it["name"]] = it

        self.assertEqual(by_source["Cargo.toml"]["serde"]["scopes"], ["workspace"])
        self.assertEqual(by_source["crates/core/Cargo.toml"]["serde"]["origin"], "workspace")

    def test_reads_the_edition_and_rust_version_a_workspace_declares_for_its_members(self):
        directory = self.workspace(**{
            "Cargo.toml": INHERITING_WORKSPACE,
            "crates/core/Cargo.toml": INHERITING_MEMBER,
        })
        facts = self.collect(directory)

        self.assertEqual(facts["edition"], "2021")
        self.assertEqual(facts["declared"], {"version": "1.76", "source": "Cargo.toml", "pinned": True})

    def test_prefers_what_the_root_package_declares_over_what_the_workspace_inherits(self):
        directory = self.workspace(**{
            "Cargo.toml": INHERITING_WORKSPACE.replace(
                "[workspace.package]",
                '[package]\nname = "widget"\nedition = "2018"\nrust-version = "1.70"\n\n[workspace.package]',
            ),
            "crates/core/Cargo.toml": INHERITING_MEMBER,
        })
        facts = self.collect(directory)

        self.assertEqual(facts["edition"], "2018")
        self.assertEqual(facts["declared"]["version"], "1.70")

    def test_leaves_an_excluded_directory_out(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "crates/core/Cargo.toml": MEMBER,
            "crates/scratch/Cargo.toml": MEMBER,
        })

        self.assertEqual([it["path"] for it in self.collect(directory)["projects"]], ["crates/core", "crates/scratch"])

    def test_honours_the_member_ceiling_it_is_given(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "crates/core/Cargo.toml": MEMBER,
        })

        facts = self.collect(directory, maxMembers="0")

        self.assertEqual(facts["projects"], [])
        self.assertEqual(facts["dropped"], 1)

    def test_drops_nothing_when_the_ceiling_is_not_reached(self):
        self.assertEqual(self.collect(self.crate())["dropped"], 0)

    def test_names_the_lock_file_when_one_is_committed(self):
        self.assertEqual(self.collect(self.crate())["lockfiles"], ["Cargo.lock"])
        self.assertEqual(self.collect(self.workspace(**{"Cargo.toml": CRATE}))["lockfiles"], [])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.crate())["dependencies"]["transitive"], [])

    def test_reports_a_manifest_that_could_not_be_read(self):
        facts = self.collect(self.workspace(**{"Cargo.toml": "[package\nname = 'a'\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "Cargo.toml")
        self.assertRegex(facts["unparsed"][0]["reason"], r"at line [0-9]+$")
        self.assertIn("could not be read", facts["incomplete"])

    def test_reports_a_member_manifest_that_could_not_be_read(self):
        directory = self.workspace(**{
            "Cargo.toml": WORKSPACE,
            "crates/core/Cargo.toml": "[package\n",
        })
        facts = self.collect(directory)

        self.assertEqual(facts["unparsed"][0]["path"], "crates/core/Cargo.toml")
        self.assertEqual(facts["projects"][0]["name"], None)

    def test_collects_nothing_where_there_is_no_cargo_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/Cargo.toml": CRATE})
        facts = self.collect(directory, projectDir="engine")

        self.assertEqual(facts["directory"], "engine")
        self.assertEqual(facts["projects"][0]["name"], "widget")


if __name__ == "__main__":
    unittest.main()
