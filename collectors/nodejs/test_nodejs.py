#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase

ROOT = {
    "name": "@company/widget",
    "version": "1.2.3",
    "packageManager": "pnpm@9.1.0",
    "engines": {"node": ">=20"},
    "workspaces": ["packages/*"],
    "scripts": {"build": "tsc --build", "test": "vitest run"},
    "dependencies": {"react": "^18.3.1", "zod": "3.23.8"},
    "devDependencies": {"typescript": "~5.4.5", "zod": "3.23.8"},
}

CORE = {"name": "@company/core", "dependencies": {"zod": "3.23.8"}}


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


class NodejsTest(CollectorTestCase):
    COLLECTOR = "nodejs"

    def project(self, **files):
        return self.workspace(**dict({
            "package.json": manifest(ROOT),
            "packages/core/package.json": manifest(CORE),
            "pnpm-lock.yaml": "lockfileVersion: \"9.0\"\n",
        }, **files))

    def test_reads_the_manifest_and_what_it_asks_for(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "package.json")
        self.assertEqual(facts["sources"], ["package.json", "packages/core/package.json"])
        self.assertEqual(facts["packageManager"], "pnpm@9.1.0")
        self.assertEqual(facts["scripts"], ["build", "test"])

    def test_reads_the_node_version_from_the_engines_field(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["declared"], {"version": ">=20", "source": "package.json", "pinned": False})

    def test_prefers_the_version_a_developer_shell_reads(self):
        facts = self.collect(self.project(**{".nvmrc": "20.11.1\n"}))

        self.assertEqual(facts["declared"], {"version": "20.11.1", "source": ".nvmrc", "pinned": True})

    def test_reads_a_node_version_file_as_well(self):
        facts = self.collect(self.project(**{".node-version": "v22.2.0\n"}))

        self.assertEqual(facts["declared"], {"version": "v22.2.0", "source": ".node-version", "pinned": True})

    def test_names_the_root_and_every_workspace_as_a_project(self):
        facts = self.collect(self.project())

        self.assertEqual(
            [(it["path"], it["manifest"], it["name"]) for it in facts["projects"]],
            [
                (".", "package.json", "@company/widget"),
                ("packages/core", "packages/core/package.json", "@company/core"),
            ],
        )

    def test_carries_every_scope_a_dependency_is_declared_in(self):
        direct = self.collect(self.project())["dependencies"]["direct"]
        by_name = dict((it["name"], it) for it in direct if it["source"] == "package.json")

        self.assertEqual(by_name["zod"]["scopes"], ["dependencies", "devDependencies"])
        self.assertEqual(by_name["react"]["scopes"], ["dependencies"])
        self.assertEqual(by_name["typescript"]["scopes"], ["devDependencies"])
        self.assertEqual(by_name["react"]["source"], "package.json")
        self.assertEqual(by_name["react"]["version"], "^18.3.1")

    def test_reads_a_caret_or_a_tilde_as_unpinned(self):
        direct = self.collect(self.project())["dependencies"]["direct"]
        by_name = dict((it["name"], it) for it in direct if it["source"] == "package.json")

        self.assertTrue(by_name["zod"]["pinned"])
        self.assertFalse(by_name["react"]["pinned"])
        self.assertFalse(by_name["typescript"]["pinned"])

    def test_reads_a_workspace_protocol_as_unpinned(self):
        document = dict(ROOT, dependencies={"@company/core": "workspace:*", "left-pad": "latest"})
        facts = self.collect(self.project(**{"package.json": manifest(document)}))
        by_name = dict((it["name"], it) for it in facts["dependencies"]["direct"])

        self.assertFalse(by_name["@company/core"]["pinned"])
        self.assertFalse(by_name["left-pad"]["pinned"])

    def test_collects_what_a_workspace_declares_too(self):
        direct = self.collect(self.project())["dependencies"]["direct"]

        self.assertIn(("zod", "packages/core/package.json"), [(it["name"], it["source"]) for it in direct])

    def test_names_every_lock_file_committed(self):
        facts = self.collect(self.project(**{"package-lock.json": "{}\n"}))

        self.assertEqual(facts["lockfiles"], ["package-lock.json", "pnpm-lock.yaml"])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.project())["dependencies"]["transitive"], [])

    def test_reports_a_workspace_manifest_that_could_not_be_read(self):
        directory = self.project(**{"packages/core/package.json": "{ not json\n"})
        facts = self.collect(directory)

        self.assertEqual(facts["unparsed"][0]["path"], "packages/core/package.json")
        self.assertIn("Expecting", facts["unparsed"][0]["reason"])
        self.assertEqual(facts["projects"][-1]["name"], None)

    def test_reports_a_root_manifest_that_could_not_be_read(self):
        facts = self.collect(self.workspace(**{"package.json": "{ not json\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "package.json")
        self.assertIn("could not be read", facts["incomplete"])

    def test_reads_the_object_form_of_workspaces(self):
        document = dict(ROOT, workspaces={"packages": ["packages/*"]})
        facts = self.collect(self.project(**{"package.json": manifest(document)}))

        self.assertEqual([it["path"] for it in facts["projects"]], [".", "packages/core"])

    def test_honours_the_workspace_ceiling_it_is_given(self):
        facts = self.collect(self.project(), maxWorkspaces="0")

        self.assertEqual([it["path"] for it in facts["projects"]], ["."])
        self.assertEqual(facts["dropped"], 1)

    def test_drops_nothing_when_the_ceiling_is_not_reached(self):
        self.assertEqual(self.collect(self.project())["dropped"], 0)

    def test_collects_nothing_where_there_is_no_node_project(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"frontend/package.json": manifest(ROOT)})
        facts = self.collect(directory, projectDir="frontend")

        self.assertEqual(facts["directory"], "frontend")
        self.assertEqual(facts["projects"][0]["name"], "@company/widget")


if __name__ == "__main__":
    unittest.main()
