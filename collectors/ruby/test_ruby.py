#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

GEMFILE = fixture("Gemfile")
LOCK = fixture("Gemfile.lock")
GEMSPEC = fixture("widget.gemspec")
GEMSPEC_WITH_REQUIRED_RUBY = fixture("widget-with-required-ruby.gemspec")


class RubyTest(CollectorTestCase):
    COLLECTOR = "ruby"

    def project(self, **files):
        return self.workspace(**dict({"Gemfile": GEMFILE, "Gemfile.lock": LOCK}, **files))

    def test_reads_the_manifest_and_the_gem_sources_it_resolves_from(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "Gemfile")
        self.assertEqual(facts["sources"], ["Gemfile"])
        self.assertEqual(facts["sources_declared"], ["https://rubygems.org"])
        self.assertEqual(facts["bundler"], "2.5.9")

    def test_says_the_gemfile_is_read_by_pattern(self):
        self.assertEqual(self.collect(self.project())["scanned"], ["Gemfile"])

    def test_reads_the_ruby_version_the_gemfile_asks_for(self):
        facts = self.collect(self.project())

        self.assertEqual(facts["declared"], {"version": "3.3.1", "source": "Gemfile", "pinned": True})

    def test_prefers_the_version_a_developer_shell_reads(self):
        facts = self.collect(self.project(**{".ruby-version": "3.2.4\n"}))

        self.assertEqual(facts["declared"], {"version": "3.2.4", "source": ".ruby-version", "pinned": True})

    def test_names_the_group_a_gem_sits_in(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["rails"]["scopes"], ["default"])
        self.assertEqual(by_name["rspec-rails"]["scopes"], ["development", "test"])
        self.assertEqual(by_name["rubocop"]["scopes"], ["development"])

    def test_reads_a_pessimistic_requirement_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertTrue(by_name["pg"]["pinned"])
        self.assertFalse(by_name["rails"]["pinned"])
        self.assertFalse(by_name["puma"]["pinned"])
        self.assertIsNone(by_name["no-version"]["version"])
        self.assertFalse(by_name["no-version"]["pinned"])

    def test_says_where_each_gem_comes_from(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["rails"]["origin"], "registry")
        self.assertEqual(by_name["queue"]["origin"], "path")
        self.assertEqual(by_name["widget"]["origin"], "git")
        self.assertEqual(by_name["rails"]["source"], "Gemfile")
        self.assertEqual(by_name["rails"]["version"], "~> 7.1.3")

    def test_reads_a_gem_inside_a_condition_as_the_top_level_group(self):
        by_name = dict((it["name"], it) for it in self.collect(self.project())["dependencies"]["direct"])

        self.assertEqual(by_name["conditional"]["scopes"], ["default"])

    def test_reads_the_gem_a_gemspec_declares(self):
        facts = self.collect(self.project(**{"widget.gemspec": GEMSPEC}))

        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "widget.gemspec", "name": "widget"}])
        self.assertEqual(facts["sources"], ["Gemfile", "widget.gemspec"])
        self.assertEqual(facts["scanned"], ["Gemfile", "widget.gemspec"])

    def test_reads_the_ruby_version_a_gemspec_requires(self):
        directory = self.workspace(**{"widget.gemspec": GEMSPEC_WITH_REQUIRED_RUBY})
        facts = self.collect(directory)

        self.assertEqual(
            facts["declared"], {"version": ">= 3.2", "source": "widget.gemspec", "pinned": False}
        )

    def test_prefers_the_gemfile_directive_over_what_a_gemspec_requires(self):
        facts = self.collect(self.project(**{"widget.gemspec": GEMSPEC_WITH_REQUIRED_RUBY}))

        self.assertEqual(facts["declared"], {"version": "3.3.1", "source": "Gemfile", "pinned": True})

    def test_names_the_project_directory_when_there_is_no_gemspec(self):
        self.assertEqual(
            self.collect(self.project())["projects"], [{"path": ".", "manifest": "Gemfile", "name": None}]
        )

    def test_names_the_lock_file_when_one_is_committed(self):
        self.assertEqual(self.collect(self.project())["lockfiles"], ["Gemfile.lock"])

        facts = self.collect(self.workspace(**{"Gemfile": GEMFILE}))

        self.assertEqual(facts["lockfiles"], [])
        self.assertIsNone(facts["bundler"])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.project())["dependencies"]["transitive"], [])

    def test_reports_a_gemspec_that_could_not_be_read(self):
        directory = self.project()
        path = os.path.join(directory, "widget.gemspec")
        os.mkdir(path)
        facts = self.collect(directory)

        self.assertEqual(
            facts["unparsed"], [{"path": "widget.gemspec", "reason": "the gemspec could not be read"}]
        )

    def test_collects_nothing_where_there_is_no_bundler_project(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"api/Gemfile": GEMFILE})
        facts = self.collect(directory, projectDir="api")

        self.assertEqual(facts["directory"], "api")
        self.assertEqual(facts["dependencies"]["direct"][0]["name"], "rails")


if __name__ == "__main__":
    unittest.main()
