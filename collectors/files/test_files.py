#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, unreadable_is_enforced


class FilesCollectorTest(CollectorTestCase):
    COLLECTOR = "files"

    def test_describes_a_file_that_is_there(self):
        directory = self.workspace(**{"README.md": "# Widget\n\nIt widgets.\n"})

        described = self.collect(directory)["files"]["README.md"]

        self.assertTrue(described["present"])
        self.assertEqual(described["lines"], 3)
        self.assertEqual(described["nonBlankLines"], 2)
        self.assertEqual(described["bytes"], len("# Widget\n\nIt widgets.\n"))

    def test_describes_a_file_that_is_missing(self):
        self.assertEqual(
            self.collect(self.workspace())["files"]["README.md"],
            {"present": False, "location": "README.md"},
        )

    def test_keys_a_file_by_the_name_it_was_asked_for_and_locates_it_from_the_root(self):
        root = self.workspace(**{"service/README.md": "# Service\n"})
        self.rooted_at(root)

        files = self.collect(os.path.join(root, "service"))["files"]

        self.assertEqual(files["README.md"]["location"], "service/README.md")
        self.assertTrue(files["README.md"]["present"])

    def test_describes_the_paths_it_is_given(self):
        directory = self.workspace(**{"docs/index.md": "# Docs\n"})

        files = self.collect(directory, paths="docs/index.md")["files"]

        self.assertEqual(list(files), ["docs/index.md"])
        self.assertTrue(files["docs/index.md"]["present"])

    def test_describes_the_extra_path_a_guardrail_asks_for(self):
        directory = self.workspace(**{"docs/index.md": "# Docs\n"})

        files = self.collect(directory, path="docs/index.md")["files"]

        self.assertTrue(files["docs/index.md"]["present"])
        self.assertIn("README.md", files)

    def link(self, directory, name, target):
        try:
            os.symlink(target.replace("/", os.sep), os.path.join(directory, name))
        except OSError as error:
            self.skip("this runner cannot create a symbolic link: %s" % error)

    def test_describes_a_file_reached_through_a_symlink(self):
        directory = self.workspace(**{"AGENTS.md": "# Agents\n\nBe careful.\n"})
        self.link(directory, "CLAUDE.md", "AGENTS.md")

        described = self.collect(directory, paths="CLAUDE.md")["files"]["CLAUDE.md"]

        self.assertTrue(described["present"])
        self.assertTrue(described["symlink"])
        self.assertEqual(described["symlinkTarget"], "AGENTS.md")
        self.assertEqual(described["lines"], 3)

    def test_describes_a_symlink_pointing_at_nothing(self):
        directory = self.workspace()
        self.link(directory, "CLAUDE.md", "AGENTS.md")

        described = self.collect(directory, paths="CLAUDE.md")["files"]["CLAUDE.md"]

        self.assertFalse(described["present"])
        self.assertTrue(described["symlink"])
        self.assertEqual(described["symlinkTarget"], "AGENTS.md")

    def test_states_a_symlink_target_in_another_directory_forward_slashed(self):
        directory = self.workspace(**{"AGENTS.md": "# Agents\n", "docs/index.md": "# Docs\n"})
        self.link(directory, "docs/CLAUDE.md", "../AGENTS.md")

        described = self.collect(directory, paths="docs/CLAUDE.md")["files"]["docs/CLAUDE.md"]

        self.assertTrue(described["present"])
        self.assertEqual(described["symlinkTarget"], "../AGENTS.md")

    def test_describes_a_file_that_is_not_a_symlink(self):
        directory = self.workspace(**{"CLAUDE.md": "# Claude\n"})

        self.assertNotIn("symlink", self.collect(directory, paths="CLAUDE.md")["files"]["CLAUDE.md"])

    def test_describes_a_file_it_cannot_read(self):
        if not unreadable_is_enforced():
            self.skip("this process reads a file whatever its mode")

        directory = self.workspace(**{"SECURITY.md": "# Security\n"})
        os.chmod(os.path.join(directory, "SECURITY.md"), 0)

        described = self.collect(directory, paths="SECURITY.md")["files"]["SECURITY.md"]

        self.assertTrue(described["present"])
        self.assertTrue(described["unreadable"])
        self.assertNotIn("lines", described)

    def test_describes_the_well_known_files_by_default(self):
        files = self.collect(self.workspace())["files"]

        self.assertIn("README.md", files)
        self.assertIn("LICENSE", files)
        self.assertIn(".gitignore", files)


if __name__ == "__main__":
    unittest.main()
