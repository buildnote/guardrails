#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

MODULE = fixture("module.mod")

BARE = fixture("bare.mod")

WORKSPACE = fixture("workspace.work")

SERVICE = fixture("service.mod")

CLI = fixture("cli.mod")

SUM = "github.com/spf13/cobra v1.8.1/go.mod h1:wHxEcudfqmLYa8iTfL+OuZPbBZkmvliBWKIezN3kD9Y=\n"


class GolangTest(CollectorTestCase):
    COLLECTOR = "golang"

    def module(self, **files):
        return self.workspace(**dict({"go.mod": MODULE, "go.sum": SUM}, **files))

    def test_reads_the_module_and_the_version_it_declares(self):
        facts = self.collect(self.module())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "go.mod")
        self.assertEqual(facts["sources"], ["go.mod"])
        self.assertEqual(facts["declared"], {"version": "1.22", "source": "go.mod", "pinned": False})
        self.assertEqual(facts["toolchain"], "go1.22.3")

    def test_names_the_module_as_the_one_project(self):
        facts = self.collect(self.module())

        self.assertEqual(
            facts["projects"], [{"path": ".", "manifest": "go.mod", "name": "github.com/company/widget"}]
        )

    def test_separates_what_the_module_requires_itself_from_what_it_pins(self):
        facts = self.collect(self.module())
        direct = facts["dependencies"]["direct"]

        self.assertEqual(
            [(it["name"], it["version"], it["scopes"], it["source"]) for it in direct],
            [
                ("github.com/spf13/cobra", "v1.8.1", ["default"], "go.mod"),
                ("golang.org/x/sync", "v0.7.0", ["default"], "go.mod"),
                ("github.com/stretchr/testify", "v1.9.0", ["default"], "go.mod"),
            ],
        )
        self.assertEqual(
            [it["name"] for it in facts["dependencies"]["transitive"]], ["github.com/spf13/pflag"]
        )

    def test_reads_a_replacement_as_a_dependency_whose_source_is_not_its_path(self):
        facts = self.collect(self.module())

        self.assertEqual(
            facts["replaced"],
            [{"name": "github.com/company/queue", "with": "./internal/queue", "source": "go.mod"}],
        )

    def test_names_the_lock_file_beside_the_manifest(self):
        self.assertEqual(self.collect(self.module())["lockfiles"], ["go.sum"])

    def test_collects_no_lock_file_when_none_is_committed(self):
        directory = self.workspace(**{"go.mod": BARE})

        self.assertEqual(self.collect(directory)["lockfiles"], [])
        self.assertEqual(self.collect(directory)["declared"]["version"], "1.21")
        self.assertIsNone(self.collect(directory)["toolchain"])

    def test_reads_every_module_a_workspace_uses(self):
        directory = self.workspace(**{
            "go.work": WORKSPACE,
            "service/go.mod": SERVICE,
            "service/go.sum": SUM,
            "cli/go.mod": CLI,
        })
        facts = self.collect(directory)

        self.assertEqual(facts["manifest"], "go.work")
        self.assertEqual(facts["sources"], ["go.work", "service/go.mod", "cli/go.mod"])
        self.assertEqual(
            [(it["path"], it["manifest"], it["name"]) for it in facts["projects"]],
            [
                ("service", "service/go.mod", "github.com/company/widget/service"),
                ("cli", "cli/go.mod", "github.com/company/widget/cli"),
            ],
        )
        self.assertEqual(facts["lockfiles"], ["service/go.sum"])
        self.assertEqual(facts["declared"], {"version": "1.22", "source": "go.work", "pinned": False})

    def test_reports_a_workspace_member_carrying_no_manifest(self):
        directory = self.workspace(**{"go.work": WORKSPACE, "service/go.mod": SERVICE})
        facts = self.collect(directory)

        self.assertEqual(
            facts["unparsed"],
            [{"path": "cli/go.mod", "reason": "no go.mod in the directory the workspace uses"}],
        )
        self.assertEqual(facts["projects"][-1], {"path": "cli", "manifest": None, "name": None})

    def test_ignores_a_commented_out_directive(self):
        directory = self.workspace(**{"go.mod": "module github.com/company/widget\n\ngo 1.22\n\n// require github.com/evil/pkg v1.0.0\n"})

        self.assertEqual(self.collect(directory)["dependencies"]["direct"], [])

    def test_collects_nothing_where_there_is_no_go_module(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"backend/go.mod": MODULE})
        facts = self.collect(directory, projectDir="backend")

        self.assertEqual(facts["directory"], "backend")
        self.assertEqual(facts["projects"][0]["name"], "github.com/company/widget")


if __name__ == "__main__":
    unittest.main()
