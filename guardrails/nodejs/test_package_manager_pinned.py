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

SIGNED = "pnpm@9.1.0+sha512.7c2ea0mm4ac81be0dbd9a4b1bb27e6ba1f4d2c9e6f8a3b0d5c1e7a2f4b6d8c0e2"


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


def without(field):
    return dict((name, value) for name, value in ROOT.items() if name != field)


class PackageManagerPinnedTest(GuardrailTestCase):
    SCRIPT = "package-manager-pinned.py"
    COLLECT = ["nodejs"]

    def project(self, **files):
        return self.workspace(**dict({
            "package.json": manifest(ROOT),
            WORKSPACE: manifest(CORE),
            "pnpm-lock.yaml": "lockfileVersion: \"9.0\"\n",
        }, **files))

    def test_passes_a_manifest_that_names_a_version(self):
        self.assert_passed(self.check(self.project()))

    def test_passes_a_manifest_that_names_the_hash_corepack_writes(self):
        self.assert_passed(self.check(self.project(**{"package.json": manifest(dict(ROOT, packageManager=SIGNED))})))

    def test_passes_a_manifest_that_names_npm(self):
        directory = self.project(**{"package.json": manifest(dict(ROOT, packageManager="npm@10.8.1"))})

        self.assert_passed(self.check(directory))

    def test_fails_a_manifest_that_names_none(self):
        directory = self.project(**{"package.json": manifest(without("packageManager"))})

        violation = self.assert_violation(self.check(directory), "names no packageManager")

        self.assertEqual(violation["evidence"], "package.json")

    def test_fails_a_bare_package_manager_name(self):
        directory = self.project(**{"package.json": manifest(dict(ROOT, packageManager="pnpm"))})

        violation = self.assert_violation(
            self.check(directory), "names the package manager as 'pnpm', which is not one exact version"
        )

        self.assertEqual(violation["evidence"], "package.json (packageManager pnpm)")

    def test_fails_a_tag_where_a_version_belongs(self):
        directory = self.project(**{"package.json": manifest(dict(ROOT, packageManager="yarn@latest"))})

        self.assert_violation(
            self.check(directory), "names the package manager as 'yarn@latest', which is not one exact version"
        )

    def test_fails_a_range_where_a_version_belongs(self):
        directory = self.project(**{"package.json": manifest(dict(ROOT, packageManager="pnpm@^9.1.0"))})

        self.assert_violation(
            self.check(directory), "names the package manager as 'pnpm@^9.1.0', which is not one exact version"
        )

    def test_skips_a_directory_with_no_node_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Node.js project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.project(), projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "frontend/package.json": manifest(ROOT),
            "package.json": manifest(without("packageManager")),
        })

        self.assert_passed(self.check(directory, projectDir="frontend"))


if __name__ == "__main__":
    unittest.main()
