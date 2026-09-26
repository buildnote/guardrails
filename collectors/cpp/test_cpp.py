#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

CMAKE = fixture("cmake.txt")

C_ONLY = fixture("c-only.txt")

DESCRIBED = fixture("described.txt")

PREFERRED = fixture("preferred.txt")

VCPKG = fixture("vcpkg.json")

CONAN = fixture("conanfile.txt")


class CppTest(CollectorTestCase):
    COLLECTOR = "cpp"

    def build(self, **files):
        return self.workspace(**dict({"CMakeLists.txt": CMAKE, "vcpkg.json": VCPKG}, **files))

    def test_reads_the_build_system_and_the_package_manager(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["directory"], ".")
        self.assertTrue(facts["exists"])
        self.assertEqual(facts["manifest"], "CMakeLists.txt")
        self.assertEqual(facts["sources"], ["CMakeLists.txt", "vcpkg.json"])
        self.assertEqual(facts["buildSystem"], "cmake")
        self.assertEqual(facts["packageManager"], "vcpkg")

    def test_says_the_cmake_script_is_read_by_pattern(self):
        self.assertEqual(self.collect(self.build())["scanned"], ["CMakeLists.txt"])

    def test_reads_the_standard_the_build_requires(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["declared"], {"version": "20", "source": "CMakeLists.txt", "pinned": True})
        self.assertEqual(facts["cmakeMinimum"], "3.25")

    def test_reads_a_standard_the_compiler_may_fall_back_from_as_unpinned(self):
        facts = self.collect(self.workspace(**{"CMakeLists.txt": PREFERRED}))

        self.assertEqual(facts["declared"], {"version": "17", "source": "CMakeLists.txt", "pinned": False})
        self.assertEqual(facts["cmakeMinimum"], "3.10")

    def test_names_the_project_and_what_it_expects_the_machine_to_carry(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "CMakeLists.txt", "name": "widget"}])
        self.assertEqual(facts["findPackages"], ["Threads", "fmt"])

    def test_reads_the_languages_a_project_call_enables(self):
        self.assertEqual(self.collect(self.workspace(**{"CMakeLists.txt": CMAKE}))["languages"], ["CXX"])

    def test_reads_a_c_only_project_as_naming_no_cxx(self):
        directory = self.workspace(**{"CMakeLists.txt": C_ONLY})

        self.assertEqual(self.collect(directory)["languages"], ["C"])

    def test_does_not_read_a_language_out_of_a_quoted_description(self):
        directory = self.workspace(**{"CMakeLists.txt": DESCRIBED})

        self.assertEqual(self.collect(directory)["languages"], ["C"])

    def test_reads_the_vcpkg_baseline_that_makes_the_build_reproducible(self):
        facts = self.collect(self.build())

        self.assertEqual(facts["baseline"], "6f3a1c2d9b8e4f7a0c5d2e1b3a4f5c6d7e8f9a0b")

    def test_reads_a_vcpkg_floor_as_unpinned(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertIsNone(by_name["fmt"]["version"])
        self.assertEqual(by_name["spdlog"]["version"], "1.13.0")
        self.assertFalse(by_name["spdlog"]["pinned"])
        self.assertEqual(by_name["spdlog"]["source"], "vcpkg.json")

    def test_names_the_feature_a_vcpkg_dependency_belongs_to(self):
        by_name = dict((it["name"], it) for it in self.collect(self.build())["dependencies"]["direct"])

        self.assertEqual(by_name["catch2"]["scopes"], ["test"])
        self.assertEqual(by_name["fmt"]["scopes"], ["default"])

    def test_reads_a_conan_manifest(self):
        facts = self.collect(self.workspace(**{"conanfile.txt": CONAN, "conan.lock": "{}\n"}))
        by_name = dict((it["name"], it) for it in facts["dependencies"]["direct"])

        self.assertEqual(facts["packageManager"], "conan")
        self.assertEqual(facts["manifest"], "conanfile.txt")
        self.assertEqual(by_name["fmt"]["version"], "10.2.1")
        self.assertTrue(by_name["fmt"]["pinned"])
        self.assertFalse(by_name["zlib"]["pinned"])
        self.assertEqual(by_name["cmake"]["scopes"], ["build"])
        self.assertEqual(by_name["catch2"]["scopes"], ["test"])
        self.assertEqual(facts["lockfiles"], ["conan.lock"])

    def test_says_the_conan_recipe_is_a_script(self):
        facts = self.collect(self.workspace(**{"conanfile.py": "from conan import ConanFile\n"}))

        self.assertEqual(facts["scanned"], ["conanfile.py"])
        self.assertEqual(facts["packageManager"], "conan")

    def test_says_when_the_checkout_carries_both_package_managers(self):
        facts = self.collect(self.build(**{"conanfile.txt": CONAN}))

        self.assertEqual(facts["packageManager"], "both")

    def test_recognises_a_build_system_that_is_not_cmake(self):
        facts = self.collect(self.workspace(**{"meson.build": "project('widget')\n", "vcpkg.json": VCPKG}))

        self.assertEqual(facts["buildSystem"], "meson")
        self.assertEqual(facts["projects"], [{"path": ".", "manifest": "vcpkg.json", "name": "widget"}])

    def test_leaves_transitive_dependencies_to_the_scanner(self):
        self.assertEqual(self.collect(self.build())["dependencies"]["transitive"], [])

    def test_reports_a_manifest_that_could_not_be_read(self):
        facts = self.collect(self.build(**{"vcpkg.json": "{ not json\n"}))

        self.assertEqual(facts["unparsed"][0]["path"], "vcpkg.json")
        self.assertIn("Expecting", facts["unparsed"][0]["reason"])

    def test_collects_nothing_where_there_is_no_cpp_build(self):
        self.assertIsNone(self.collect(self.workspace(**{"pom.xml": "<project/>\n"})))

    def test_reports_a_project_directory_that_is_not_a_directory(self):
        facts = self.collect(self.workspace(), projectDir="missing")

        self.assertFalse(facts["exists"])
        self.assertEqual(facts["incomplete"], "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/CMakeLists.txt": CMAKE})
        facts = self.collect(directory, projectDir="engine")

        self.assertEqual(facts["directory"], "engine")
        self.assertEqual(facts["projects"][0]["name"], "widget")


if __name__ == "__main__":
    unittest.main()
