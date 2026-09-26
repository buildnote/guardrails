#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CMAKE = fixture("cmake-lists.txt")

VCPKG = fixture("vcpkg.json")

CONAN = fixture("conanfile.txt")


class PackageManagerDeclaredTest(GuardrailTestCase):
    SCRIPT = "package-manager-declared.py"
    COLLECT = ["cpp"]

    def test_passes_a_build_that_declares_its_packages_to_vcpkg(self):
        directory = self.workspace(**{"CMakeLists.txt": CMAKE, "vcpkg.json": VCPKG})

        self.assert_passed(self.check(directory))

    def test_passes_a_build_that_declares_them_to_conan(self):
        directory = self.workspace(**{"CMakeLists.txt": CMAKE, "conanfile.txt": CONAN})

        self.assert_passed(self.check(directory))

    def test_fails_a_build_that_expects_the_machine_to_carry_them(self):
        directory = self.workspace(**{"CMakeLists.txt": CMAKE})

        violation = self.assert_violation(self.check(directory), "declares no package manager")

        self.assertEqual(violation["evidence"], "CMakeLists.txt")

    def test_skips_a_directory_with_no_cpp_build(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no C or C++ build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        directory = self.workspace(**{"CMakeLists.txt": CMAKE, "vcpkg.json": VCPKG})

        self.assert_skipped(self.check(directory, projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{
            "engine/CMakeLists.txt": CMAKE,
            "engine/vcpkg.json": VCPKG,
        })

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
