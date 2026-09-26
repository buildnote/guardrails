#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

ROOT = {
    "name": "@company/widget",
    "version": "1.2.3",
    "packageManager": "pnpm@9.1.0",
    "engines": {"node": ">=20"},
    "workspaces": ["packages/*"],
    "scripts": {"build": "tsc --build", "test": "vitest run"},
    "dependencies": {"react": "^18.3.1", "zod": "3.23.8"},
    "devDependencies": {"typescript": "~5.4.5"},
}

CORE = {"name": "@company/core", "version": "1.2.3", "dependencies": {"zod": "3.23.8"}}

WORKSPACE = "packages/core/package.json"


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


def without(field):
    return dict((name, value) for name, value in ROOT.items() if name != field)


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["nodejs"]

    def project(self, **files):
        return self.workspace(**dict({
            "package.json": manifest(ROOT),
            WORKSPACE: manifest(CORE),
            "pnpm-lock.yaml": "lockfileVersion: \"9.0\"\n",
        }, **files))

    def test_passes_a_project_that_declares_an_engines_range(self):
        self.assert_passed(self.check(self.project()))

    def test_passes_a_project_that_declares_an_nvmrc(self):
        directory = self.project(**{"package.json": manifest(without("engines")), ".nvmrc": "20.11.1\n"})

        self.assert_passed(self.check(directory))

    def test_passes_a_project_that_declares_a_node_version_file(self):
        directory = self.project(**{"package.json": manifest(without("engines")), ".node-version": "v22.2.0\n"})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_declares_none(self):
        directory = self.project(**{"package.json": manifest(without("engines"))})

        violation = self.assert_violation(self.check(directory), "No Node.js version declared in package.json")

        self.assertEqual(violation["evidence"], "package.json")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.project(**{"package.json": manifest(dict(ROOT, engines={"node": ">=16"}))})

        violation = self.assert_violation(self.check(directory), "asks for Node.js >=16, older than the 18 expected")

        self.assertEqual(violation["evidence"], "package.json (Node.js >=16)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.project()

        self.assert_passed(self.check(directory, minVersion="20"))
        self.assert_violation(self.check(directory, minVersion="22"), "older than the 22 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.project(**{"package.json": manifest(without("engines")), ".nvmrc": "20.11\n"})

        self.assert_passed(self.check(directory, minVersion="20.11.0"))
        self.assert_violation(self.check(directory, minVersion="20.11.1"), "older than the 20.11.1 expected")

    def test_reads_a_leading_v_as_the_version_it_names(self):
        directory = self.project(**{"package.json": manifest(without("engines")), ".node-version": "v22.2.0\n"})

        self.assert_passed(self.check(directory, minVersion="22"))

        violation = self.assert_violation(self.check(directory, minVersion="24"), "asks for Node.js v22.2.0")

        self.assertEqual(violation["evidence"], ".node-version (Node.js v22.2.0)")

    def test_skips_a_directory_with_no_node_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Node.js project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.project(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"frontend/package.json": manifest(ROOT)})

        self.assert_passed(self.check(directory, projectDir="frontend"))


if __name__ == "__main__":
    unittest.main()
