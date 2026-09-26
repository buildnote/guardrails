#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, slashed


class GitCollectorTest(CollectorTestCase):
    COLLECTOR = "git"

    def test_collects_the_commits_in_the_range(self):
        directory = self.repository()
        base = self.head(directory)
        self.commit(directory, "feat: add a widget\n\nThe body.")
        self.commit(directory, "fix: repair the widget")

        facts = self.collect(directory, baseRef=base)

        self.assertTrue(facts["repository"])
        self.assertTrue(facts["resolved"])
        self.assertEqual(facts["baseRef"], base)
        self.assertEqual(facts["baseSha"], base)
        self.assertEqual(
            [commit["subject"] for commit in facts["commits"]],
            ["fix: repair the widget", "feat: add a widget"],
        )

    def test_collects_the_whole_message_of_a_commit(self):
        directory = self.repository()
        base = self.head(directory)
        self.commit(directory, "feat: add a widget\n\nThe body.\n\nBREAKING CHANGE: it replaces the gadget.")

        commit = self.collect(directory, baseRef=base)["commits"][0]

        self.assertEqual(commit["message"], "feat: add a widget\n\nThe body.\n\nBREAKING CHANGE: it replaces the gadget.")
        self.assertEqual(commit["body"], "The body.\n\nBREAKING CHANGE: it replaces the gadget.")
        self.assertEqual(commit["short"], commit["sha"][:7])
        self.assertFalse(commit["merge"])
        self.assertEqual(commit["author"]["email"], "guardrails@buildnote.io")
        self.assertEqual(commit["committer"]["name"], "Guardrails")

    def test_marks_a_merge_commit(self):
        directory = self.repository()
        base = self.head(directory)
        trunk = self.git(directory, "rev-parse", "--abbrev-ref", "HEAD").strip()

        self.git(directory, "checkout", "--quiet", "-b", "side")
        self.commit(directory, "feat: add a widget on the side")
        self.git(directory, "checkout", "--quiet", trunk)
        self.commit(directory, "fix: repair the widget on the trunk")
        self.git(directory, "merge", "--quiet", "--no-ff", "--no-edit", "side")

        commits = self.collect(directory, baseRef=base)["commits"]
        merges = [commit for commit in commits if commit["merge"]]

        self.assertEqual(len(merges), 1)
        self.assertEqual(len(merges[0]["parents"]), 2)

    def test_collects_the_files_the_range_changed(self):
        directory = self.repository()
        base = self.head(directory)
        self.write(directory, "src/widget.kt", "fun widget() {}\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: add a widget")

        self.assertEqual(self.collect(directory, baseRef=base)["changedFiles"], ["src/widget.kt"])

    def test_collects_a_changed_path_holding_spaces(self):
        directory = self.repository()
        base = self.head(directory)
        spaced = "src/GetBuildEventsV1Test.should filter build events.approved"
        self.write(directory, spaced, "approved\n")
        self.write(directory, "src/widget.kt", "fun widget() {}\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "test: add an approval")

        self.assertEqual(
            sorted(self.collect(directory, baseRef=base)["changedFiles"]),
            ["src/GetBuildEventsV1Test.should filter build events.approved", "src/widget.kt"]
        )

    def test_collects_the_lines_the_range_changed(self):
        directory = self.repository()
        self.write(directory, "src/widget.kt", "one\ntwo\nthree\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: add a widget")
        base = self.head(directory)

        self.write(directory, "src/widget.kt", "one\ntwo prime\n")
        self.write(directory, "src/gadget.kt", "fun gadget() {}\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: add a gadget")

        changes = dict((change["path"], change) for change in self.collect(directory, baseRef=base)["changes"])

        self.assertEqual(changes["src/widget.kt"]["added"], 1)
        self.assertEqual(changes["src/widget.kt"]["deleted"], 2)
        self.assertFalse(changes["src/widget.kt"]["binary"])
        self.assertEqual(changes["src/gadget.kt"]["added"], 1)
        self.assertEqual(changes["src/gadget.kt"]["deleted"], 0)

    def test_counts_the_lines_of_a_path_holding_spaces(self):
        directory = self.repository()
        base = self.head(directory)
        spaced = "src/GetBuildEventsV1Test.should filter build events.approved"
        self.write(directory, spaced, "approved\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "test: add an approval")

        facts = self.collect(directory, baseRef=base)

        self.assertEqual([change["path"] for change in facts["changes"]], [spaced])
        self.assertEqual(facts["changedFiles"], [change["path"] for change in facts["changes"]])

    def test_counts_a_rename_under_the_path_it_was_renamed_to(self):
        directory = self.repository()
        self.write(directory, "src/old.kt", "one\ntwo\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "feat: add a widget")
        base = self.head(directory)

        self.git(directory, "mv", "src/old.kt", "src/new.kt")
        self.write(directory, "src/new.kt", "one\ntwo\nthree\n")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "refactor: rename the widget")

        facts = self.collect(directory, baseRef=base)

        self.assertEqual([change["path"] for change in facts["changes"]], ["src/new.kt"])
        self.assertEqual(facts["changes"][0]["added"], 1)
        self.assertEqual(facts["changes"][0]["deleted"], 0)

    def test_counts_no_lines_for_a_binary_file(self):
        directory = self.repository()
        base = self.head(directory)
        self.write(directory, "logo.bin", "\x00\x01buildnote\x00")
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "chore: add a logo")

        change = self.collect(directory, baseRef=base)["changes"][0]

        self.assertEqual(change["path"], "logo.bin")
        self.assertTrue(change["binary"])
        self.assertIsNone(change["added"])
        self.assertIsNone(change["deleted"])

    def test_collects_the_head_and_the_remotes(self):
        directory = self.repository()
        self.git(directory, "remote", "add", "origin", "git@github.com:buildnote/widget.git")
        self.git(directory, "tag", "v1.0.0")

        facts = self.collect(directory, baseRef=self.head(directory))

        self.assertEqual(facts["head"]["sha"], self.head(directory))
        self.assertEqual(facts["head"]["short"], self.head(directory)[:7])
        self.assertFalse(facts["head"]["detached"])
        self.assertEqual(facts["head"]["tags"], ["v1.0.0"])
        self.assertEqual(facts["remotes"], {"origin": "git@github.com:buildnote/widget.git"})
        self.assertFalse(facts["dirty"])
        self.assertEqual(facts["root"], slashed(os.path.realpath(directory)))

    def test_reports_a_dirty_working_tree(self):
        directory = self.repository()
        self.write(directory, "widget.txt", "uncommitted\n")

        self.assertTrue(self.collect(directory, baseRef=self.head(directory))["dirty"])

    def test_reports_an_unresolvable_base_ref(self):
        facts = self.collect(self.repository(), baseRef="buildnote/not-a-real-ref")

        self.assertTrue(facts["repository"])
        self.assertFalse(facts["resolved"])
        self.assertEqual(facts["commits"], [])
        self.assertEqual(facts["changedFiles"], [])
        self.assertEqual(facts["changes"], [])

    def test_reports_no_repository(self):
        facts = self.collect(self.workspace())

        self.assertFalse(facts["repository"])
        self.assertEqual(facts["incomplete"], "not a git repository")


if __name__ == "__main__":
    unittest.main()
