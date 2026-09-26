#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CMAKE = fixture("cmake.txt")

WITHOUT_MINIMUM = fixture("without-minimum.txt")

VCPKG = fixture("vcpkg.json")


class CmakeMinimumFloorTest(GuardrailTestCase):
    SCRIPT = "cmake-minimum-floor.py"
    COLLECT = ["cpp"]

    def build(self, **files):
        return self.workspace(**dict({"CMakeLists.txt": CMAKE, "vcpkg.json": VCPKG}, **files))

    def test_passes_a_build_that_requires_a_recent_cmake(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_floor_older_than_the_one_expected(self):
        directory = self.build(**{"CMakeLists.txt": CMAKE.replace("VERSION 3.25", "VERSION 3.10")})

        violation = self.assert_violation(self.check(directory), "configures under CMake 3.10 policies, older than the 3.20 expected")

        self.assertEqual(violation["evidence"], "CMakeLists.txt (CMake 3.10)")

    def test_fails_a_build_that_names_no_floor(self):
        directory = self.build(**{"CMakeLists.txt": WITHOUT_MINIMUM})

        violation = self.assert_violation(self.check(directory), "names no cmake_minimum_required")

        self.assertEqual(violation["evidence"], "CMakeLists.txt")

    def test_honours_the_floor_it_is_given(self):
        directory = self.build()

        self.assert_passed(self.check(directory, minVersion="3.25"))
        self.assert_violation(self.check(directory, minVersion="3.26"), "older than the 3.26 expected")

    def test_compares_versions_of_unequal_length(self):
        directory = self.build()

        self.assert_passed(self.check(directory, minVersion="3.25.0"))
        self.assert_violation(self.check(directory, minVersion="3.25.1"), "older than the 3.25.1 expected")

    def test_passes_a_build_that_declares_a_policy_range(self):
        directory = self.build(**{"CMakeLists.txt": CMAKE.replace("VERSION 3.25", "VERSION 3.16...3.28")})

        self.assert_passed(self.check(directory))

    def test_reads_the_policy_version_of_a_range_that_is_too_old(self):
        directory = self.build(**{"CMakeLists.txt": CMAKE.replace("VERSION 3.25", "VERSION 3.5...3.10")})

        violation = self.assert_violation(self.check(directory), "configures under CMake 3.10 policies, older than the 3.20 expected")

        self.assertEqual(violation["evidence"], "CMakeLists.txt (CMake 3.10)")

    def test_skips_a_build_that_is_not_cmake(self):
        directory = self.workspace(**{"meson.build": "project('widget', 'cpp')\n", "vcpkg.json": VCPKG})

        self.assert_skipped(self.check(directory), "is not a CMake build")

    def test_skips_a_directory_with_no_cpp_build(self):
        self.assert_skipped(self.check(self.workspace(**{"main.go": "package main\n"})), "no C or C++ build in .")

    def test_skips_a_project_directory_that_is_not_a_directory(self):
        self.assert_skipped(self.check(self.build(), projectDir="missing"), "missing is not a directory")

    def test_honours_the_project_directory_it_is_given(self):
        directory = self.workspace(**{"engine/CMakeLists.txt": CMAKE})

        self.assert_passed(self.check(directory, projectDir="engine"))


if __name__ == "__main__":
    unittest.main()
