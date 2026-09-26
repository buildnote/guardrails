#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase

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

WITHOUT_VERSION = dict(COMPOSER, require={"ext-json": "*", "symfony/console": "^7.0"})

ON_PLATFORM = dict(WITHOUT_VERSION, config={"platform": {"php": "8.2.18"}})

ON_SEVEN = dict(COMPOSER, require=dict(COMPOSER["require"], php="^7.4"))


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


class VersionDeclaredTest(GuardrailTestCase):
    SCRIPT = "version-declared.py"
    COLLECT = ["php"]

    def test_passes_a_project_that_requires_a_php_version(self):
        self.assert_passed(self.check(self.workspace(**{"composer.json": manifest(COMPOSER)})))

    def test_passes_a_project_that_pins_the_platform_composer_resolves_against(self):
        self.assert_passed(self.check(self.workspace(**{"composer.json": manifest(ON_PLATFORM)})))

    def test_fails_a_project_that_declares_none(self):
        directory = self.workspace(**{"composer.json": manifest(WITHOUT_VERSION)})

        violation = self.assert_violation(self.check(directory), "No PHP version declared in composer.json")

        self.assertEqual(violation["evidence"], "composer.json")

    def test_fails_a_version_older_than_the_floor(self):
        directory = self.workspace(**{"composer.json": manifest(ON_SEVEN)})

        violation = self.assert_violation(self.check(directory), "asks for PHP ^7.4, older than the 8.1 expected")

        self.assertEqual(violation["evidence"], "composer.json (PHP ^7.4)")

    def test_honours_the_floor_it_is_given(self):
        directory = self.workspace(**{"composer.json": manifest(COMPOSER)})

        self.assert_passed(self.check(directory, minVersion="8.2"))
        self.assert_violation(self.check(directory, minVersion="8.3"), "older than the 8.3 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.workspace(**{"composer.json": manifest(ON_PLATFORM)})

        self.assert_passed(self.check(directory, minVersion="8.2"))
        self.assert_violation(self.check(directory, minVersion="8.2.19"), "older than the 8.2.19 expected")

    def test_skips_a_directory_with_no_composer_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Composer project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"composer.json": manifest(COMPOSER)})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/composer.json": manifest(COMPOSER)})

        self.assert_passed(self.check(directory, projectDir="api"))


if __name__ == "__main__":
    unittest.main()
