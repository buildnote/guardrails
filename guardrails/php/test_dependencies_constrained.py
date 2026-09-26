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
        "lib-openssl": ">=3.0",
        "symfony/console": "^7.0",
        "monolog/monolog": "3.6.0",
    },
    "require-dev": {"phpunit/phpunit": "^11.1"},
    "scripts": {"test": "phpunit"},
}

RANGES = dict(COMPOSER, require={
    "php": "^8.2",
    "symfony/console": "^7.0",
    "guzzlehttp/guzzle": "~7.8.0",
    "monolog/monolog": ">=3.0 <4.0",
})

ANYTHING = dict(COMPOSER, require=dict(COMPOSER["require"], **{"company/queue": "*"}))

ANYTHING_IN_DEV = dict(COMPOSER, **{"require-dev": {"phpunit/phpunit": "*"}})


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


class DependenciesConstrainedTest(GuardrailTestCase):
    SCRIPT = "dependencies-constrained.py"
    COLLECT = ["php"]

    def test_passes_a_project_whose_requirements_all_carry_a_constraint(self):
        self.assert_passed(self.check(self.workspace(**{"composer.json": manifest(COMPOSER)})))

    def test_passes_ranges_rather_than_asking_for_pins(self):
        self.assert_passed(self.check(self.workspace(**{"composer.json": manifest(RANGES)})))

    def test_fails_a_package_required_as_anything(self):
        directory = self.workspace(**{"composer.json": manifest(ANYTHING)})

        violation = self.assert_violation(self.check(directory), "company/queue asks for * in composer.json")

        self.assertEqual(violation["evidence"], "company/queue (composer.json)")

    def test_fails_a_development_package_required_as_anything(self):
        directory = self.workspace(**{"composer.json": manifest(ANYTHING_IN_DEV)})

        self.assert_violation(self.check(directory), "phpunit/phpunit asks for * in composer.json")

    def test_ignores_the_platform_requirements_composer_does_not_install(self):
        document = dict(COMPOSER, require={"php": "*", "ext-json": "*", "symfony/console": "^7.0"})

        self.assert_passed(self.check(self.workspace(**{"composer.json": manifest(document)})))

    def test_skips_a_directory_with_no_composer_project(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no Composer project in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"composer.json": manifest(COMPOSER)})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/composer.json": manifest(ANYTHING)})

        self.assert_violation(self.check(directory, projectDir="api"), "company/queue asks for *")


if __name__ == "__main__":
    unittest.main()
