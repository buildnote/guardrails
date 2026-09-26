#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

PYPROJECT = fixture("pyproject.toml")

MEMBER = fixture("member.toml")

POETRY = fixture("poetry.toml")

SETUP_CFG = fixture("setup.cfg")

REQUIREMENTS = fixture("requirements.txt")


class PythonTest(CollectorTestCase):
    COLLECTOR = "python"

    def project(self, **files):
        return self.workspace(**dict({"pyproject.toml": PYPROJECT}, **files))

    def test_reads_the_manifest_and_the_backend_it_names(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "pyproject.toml")
        self.assertEqual(facts["backend"], "hatchling.build")
        self.assertEqual(facts["packaging"], "pep621")
        self.assertEqual(facts["sources"], ["pyproject.toml"])

    def test_reads_the_python_version_the_project_requires(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["declared"], {"version": ">=3.11", "source": "pyproject.toml", "pinned": False})

    def test_prefers_the_version_a_developer_shell_reads(self):
        facts = self.collect(self.project(**{".python-version": "3.12.2\n"}))

        self.assertEqual(facts["declared"], {"version": "3.12.2", "source": ".python-version", "pinned": True})

    def test_normalises_a_distribution_name_the_way_the_index_does(self):
        directory = self.project(**{"pyproject.toml": POETRY})
        names = [it["name"] for it in self.collect(directory)["dependencies"]["direct"]]

        self.assertIn("zope-interface", names)

    def test_reads_a_requirement_with_its_constraint_and_marker(self):
        direct = self.collect(self.project())["dependencies"]["direct"]
        by_name = dict((it["name"], it) for it in direct)

        self.assertEqual(by_name["httpx"]["version"], ">=0.27")
        self.assertEqual(by_name["httpx"]["scopes"], ["default"])
        self.assertEqual(by_name["httpx"]["source"], "pyproject.toml")
        self.assertIsNone(by_name["httpx"]["marker"])
        self.assertEqual(by_name["tomli"]["marker"], 'python_version < "3.11"')

    def test_reads_only_double_equals_as_pinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertTrue(by_name["ruff"]["pinned"])
        self.assertTrue(by_name["tomli"]["pinned"])
        self.assertFalse(by_name["httpx"]["pinned"])
        self.assertFalse(by_name["pydantic"]["pinned"])

    def test_names_an_extra_as_the_scope_that_declares_it(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["pytest"]["scopes"], ["dev"])

    def test_reads_a_poetry_project(self):
        facts = self.collect(self.project(**{"pyproject.toml": POETRY}))
        by_name = dict((it["name"], it) for it in facts["dependencies"]["direct"])

        self.assertEqual(facts["packaging"], "poetry")
        self.assertIsNone(facts["backend"])
        self.assertEqual(facts["declared"]["version"], "^3.11")
        self.assertEqual(by_name["pytest"]["scopes"], ["dev"])
        self.assertTrue(by_name["pytest"]["pinned"])
        self.assertFalse(by_name["httpx"]["pinned"])

    def test_reads_every_member_of_a_workspace(self):
        directory = self.project(**{"packages/core/pyproject.toml": MEMBER})
        facts = self.collect(directory)

        self.assertEqual(
            [(it["path"], it["manifest"], it["name"]) for it in facts["projects"]],
            [(".", "pyproject.toml", "widget"), ("packages/core", "packages/core/pyproject.toml", "widget-core")],
        )
        self.assertIn(
            ("anyio", "packages/core/pyproject.toml"),
            [(it["name"], it["source"]) for it in facts["dependencies"]["direct"]],
        )

    def test_reads_a_setuptools_project(self):
        facts = self.collect(self.workspace(**{"setup.cfg": SETUP_CFG}))
        names = [it["name"] for it in facts["dependencies"]["direct"]]

        self.assertEqual(facts["packaging"], "setuptools")
        self.assertEqual(facts["manifest"], "setup.cfg")
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "setup.cfg", "name": "widget"}])
        self.assertEqual(facts["declared"]["version"], ">=3.10")
        self.assertEqual(names, ["httpx", "pydantic"])

    def test_says_a_setup_script_is_code_rather_than_a_declaration(self):
        facts = self.collect(self.workspace(**{"setup.py": "from setuptools import setup\nsetup()\n"}))

        self.assertEqual(
            facts["unparsed"],
            [{"path": "setup.py", "reason": "setup.py is Python rather than a declaration and is not read"}],
        )

    def test_reads_a_requirements_file(self):
        facts = self.collect(self.workspace(**{"requirements.txt": REQUIREMENTS}))
        direct = facts["dependencies"]["direct"]

        self.assertEqual(facts["packaging"], "requirements")
        self.assertEqual(facts["requirements"], ["requirements.txt"])
        self.assertEqual([(it["name"], it["scopes"]) for it in direct], [("httpx", ["requirements"]), ("pydantic", ["requirements"])])
        self.assertTrue(all(it["pinned"] for it in direct))

    def test_honours_the_requirements_globs_it_is_given(self):
        directory = self.workspace(**{
            "pyproject.toml": PYPROJECT,
            "requirements/dev.txt": "pytest==8.2.0\n",
        })

        self.assertEqual(self.collect(directory)["requirements"], ["requirements/dev.txt"])
        self.assertEqual(self.collect(directory, requirements="none/*.txt")["requirements"], [])

    def test_names_every_lock_file_committed(self):
        facts = self.collect(self.project(**{"uv.lock": "version = 1\n", "poetry.lock": "\n"}))

        self.assertEqual(facts["lockfiles"], ["poetry.lock", "uv.lock"])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.project())["dependencies"]["transitive"], [])

    def test_reports_a_manifest_that_could_not_be_read(self):
        facts = self.collect(self.workspace(**{"pyproject.toml": "[project\nname = 'a'\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "pyproject.toml")
        self.assertRegex(facts["unparsed"][0]["reason"], r"at line [0-9]+$")

    def test_collects_nothing_where_there_is_no_python_project(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"backend/pyproject.toml": PYPROJECT})
        facts = self.collect(directory, projectDir="backend")

        self.assertEqual(facts["directory"], "backend")
        self.assertEqual(facts["projects"][0]["name"], "widget")


if __name__ == "__main__":
    unittest.main()
