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

PNPM_LOCK = "lockfileVersion: \"9.0\"\n"

NPM_LOCK = "{\n  \"name\": \"@company/widget\",\n  \"lockfileVersion\": 3\n}\n"

YARN_LOCK = "__metadata:\n  version: 8\n"


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


class SinglePackageManagerTest(GuardrailTestCase):
    SCRIPT = "single-package-manager.py"
    COLLECT = ["nodejs"]

    def project(self, **files):
        return self.workspace(**dict({"package.json": manifest(ROOT), WORKSPACE: manifest(CORE)}, **files))

    def test_passes_a_project_that_commits_one(self):
        self.assert_passed(self.check(self.project(**{"pnpm-lock.yaml": PNPM_LOCK})))

    def test_passes_a_project_that_commits_none(self):
        self.assert_passed(self.check(self.project()))

    def test_fails_a_project_that_commits_two(self):
        directory = self.project(**{"pnpm-lock.yaml": PNPM_LOCK, "package-lock.json": NPM_LOCK})

        violation = self.assert_violation(self.check(directory), "commits 2 lock files")

        self.assertEqual(violation["evidence"], "package-lock.json, pnpm-lock.yaml")

    def test_fails_a_project_that_commits_three(self):
        directory = self.project(**{
            "pnpm-lock.yaml": PNPM_LOCK,
            "package-lock.json": NPM_LOCK,
            "yarn.lock": YARN_LOCK,
        })

        violation = self.assert_violation(self.check(directory), "commits 3 lock files")

        self.assertEqual(violation["evidence"], "package-lock.json, pnpm-lock.yaml, yarn.lock")

    def test_skips_a_directory_with_no_node_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Node.js project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.project(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "frontend/package.json": manifest(ROOT),
            "frontend/pnpm-lock.yaml": PNPM_LOCK,
            "package-lock.json": NPM_LOCK,
        })

        self.assert_passed(self.check(directory, projectDir="frontend"))


if __name__ == "__main__":
    unittest.main()
