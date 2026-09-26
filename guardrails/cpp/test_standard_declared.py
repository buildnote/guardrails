#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CMAKE = fixture("cmake.txt")

WITHOUT_STANDARD = fixture("standard-declared-without-standard.txt")

VCPKG = fixture("vcpkg.json")

C_ONLY = fixture("c-only.txt")


class StandardDeclaredTest(GuardrailTestCase):
    SCRIPT = "standard-declared.py"
    COLLECT = ["cpp"]

    def build(self, **files):
        return self.workspace(**dict({"CMakeLists.txt": CMAKE, "vcpkg.json": VCPKG}, **files))

    def test_passes_a_build_that_declares_the_standard(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_build_that_declares_none(self):
        directory = self.build(**{"CMakeLists.txt": WITHOUT_STANDARD})

        violation = self.assert_violation(self.check(directory), "declares no C++ standard")

        self.assertEqual(violation["evidence"], "CMakeLists.txt")

    def test_fails_a_standard_older_than_the_floor(self):
        directory = self.build(**{"CMakeLists.txt": CMAKE.replace("STANDARD 20", "STANDARD 11")})

        violation = self.assert_violation(self.check(directory), "asks for C++11, older than the C++17 expected")

        self.assertEqual(violation["evidence"], "CMakeLists.txt (C++11)")

    def test_reads_a_standard_named_by_its_last_century_year_as_the_oldest(self):
        directory = self.build(**{"CMakeLists.txt": CMAKE.replace("STANDARD 20", "STANDARD 98")})

        self.assert_violation(self.check(directory), "asks for C++98, older than the C++17 expected")

    def test_honours_the_floor_it_is_given(self):
        directory = self.build()

        self.assert_passed(self.check(directory, minStandard="20"))
        self.assert_violation(self.check(directory, minStandard="23"), "older than the C++23 expected")

    def test_skips_a_floor_that_is_not_a_number(self):
        self.assert_skipped(self.check(self.build(), minStandard="c++20"), "minStandard 'c++20' is not a number")

    def test_skips_a_checkout_with_no_cmake_build_to_read_the_standard_from(self):
        directory = self.workspace(**{"conanfile.txt": "[requires]\nfmt/10.2.1\n"})

        self.assert_skipped(self.check(directory), "is not a CMake build")

    def test_skips_a_build_whose_build_system_the_collector_does_not_read(self):
        directory = self.workspace(**{"meson.build": "project('widget', 'cpp')\n", "vcpkg.json": VCPKG})

        self.assert_skipped(self.check(directory), "the standard is only read from CMakeLists.txt")

    def test_skips_a_c_only_build_that_has_no_cxx_standard_to_declare(self):
        directory = self.workspace(**{"CMakeLists.txt": C_ONLY})

        self.assert_skipped(self.check(directory), "enables C rather than C++")

    def test_skips_a_directory_with_no_cpp_build(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no C or C++ build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/CMakeLists.txt": CMAKE})

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
