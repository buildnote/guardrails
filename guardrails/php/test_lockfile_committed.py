#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

COMPOSER = {
    "name": "company/widget",
    "type": "project",
    "require": {
        "php": "^8.2",
        "ext-json": "*",
        "symfony/console": "^7.0",
        "monolog/monolog": "3.6.0",
    },
    "require-dev": {"phpunit/phpunit": "^11.1"},
    "scripts": {"test": "phpunit"},
}

LOCKFILE = fixture("lockfile.json")


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


class LockfileCommittedTest(GuardrailTestCase):
    SCRIPT = "lockfile-committed.py"
    COLLECT = ["php"]

    def test_passes_a_project_that_commits_composer_lock(self):
        directory = self.workspace(**{"composer.json": manifest(COMPOSER), "composer.lock": LOCKFILE})

        self.assert_passed(self.check(directory))

    def test_fails_a_project_that_commits_none(self):
        directory = self.workspace(**{"composer.json": manifest(COMPOSER)})

        violation = self.assert_violation(self.check(directory), "commits no lock file")

        self.assertEqual(violation["evidence"], "composer.json")

    def test_skips_a_directory_with_no_composer_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Composer project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"composer.json": manifest(COMPOSER), "composer.lock": LOCKFILE})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "api/composer.json": manifest(COMPOSER),
            "api/composer.lock": LOCKFILE,
        })

        self.assert_passed(self.check(directory, projectDir="api"))


if __name__ == "__main__":
    unittest.main()
