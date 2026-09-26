#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase

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
    "require-dev": {"phpunit/phpunit": "^11.1", "monolog/monolog": "3.6.0"},
    "scripts": {"test": "phpunit", "lint": "php-cs-fixer fix --dry-run"},
}


def manifest(document):
    return json.dumps(document, indent=2) + "\n"


class PhpTest(CollectorTestCase):
    COLLECTOR = "php"

    def project(self, **files):
        return self.workspace(**dict({
            "composer.json": manifest(COMPOSER),
            "composer.lock": "{\"packages\": []}\n",
        }, **files))

    def test_reads_the_manifest_and_the_package_it_declares(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "composer.json")
        self.assertEqual(facts["sources"], ["composer.json"])
        self.assertEqual(facts["type"], "project")
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "composer.json", "name": "company/widget"}])
        self.assertEqual(facts["scripts"], ["lint", "test"])

    def test_reads_the_php_constraint_the_project_requires(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["declared"], {"version": "^8.2", "source": "composer.json", "pinned": False})

    def test_prefers_the_platform_composer_resolves_against(self):
        document = dict(COMPOSER, config={"platform": {"php": "8.2.18"}})
        facts = self.collect(self.project(**{"composer.json": manifest(document)}))

        self.assertEqual(facts["declared"], {"version": "8.2.18", "source": "composer.json", "pinned": True})

    def test_keeps_platform_requirements_out_of_the_packages(self):
        facts = self.collect(self.project())
        names = [it["name"] for it in facts["dependencies"]["direct"]]

        self.assertNotIn("php", names)
        self.assertNotIn("ext-json", names)
        self.assertEqual(
            facts["platform"], [{"name": "ext-json", "version": "*"}, {"name": "lib-openssl", "version": ">=3.0"}]
        )

    def test_carries_every_scope_a_package_is_required_in(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["monolog/monolog"]["scopes"], ["require", "require-dev"])
        self.assertEqual(by_name["phpunit/phpunit"]["scopes"], ["require-dev"])
        self.assertEqual(by_name["symfony/console"]["source"], "composer.json")

    def test_reads_a_caret_constraint_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertTrue(by_name["monolog/monolog"]["pinned"])
        self.assertFalse(by_name["symfony/console"]["pinned"])

    def test_reads_a_development_branch_as_unpinned(self):
        document = dict(COMPOSER, require={"company/queue": "dev-main"})
        facts = self.collect(self.project(**{"composer.json": manifest(document)}))

        self.assertFalse(facts["dependencies"]["direct"][0]["pinned"])

    def test_names_the_lock_file_when_one_is_committed(self):
        self.assertEqual(self.collect(self.project())["lockfiles"], ["composer.lock"])
        self.assertEqual(self.collect(self.workspace(**{"composer.json": manifest(COMPOSER)}))["lockfiles"], [])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.project())["dependencies"]["transitive"], [])

    def test_reports_a_manifest_that_could_not_be_read(self):
        facts = self.collect(self.workspace(**{"composer.json": "{ not json\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "composer.json")
        self.assertIn("Expecting", facts["unparsed"][0]["reason"])
        self.assertIn("could not be read", facts["incomplete"])

    def test_collects_nothing_where_there_is_no_composer_project(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/composer.json": manifest(COMPOSER)})
        facts = self.collect(directory, projectDir="api")

        self.assertEqual(facts["directory"], "api")
        self.assertEqual(facts["projects"][0]["name"], "company/widget")


if __name__ == "__main__":
    unittest.main()
