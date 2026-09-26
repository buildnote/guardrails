#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, fixtures

fixture = fixtures(__file__)

CMAKE = fixture("cmake.txt")

PREFERRED = fixture("preferred.txt")

WITHOUT_STANDARD = fixture("standard-required-without-standard.txt")

VCPKG = fixture("vcpkg.json")

C_ONLY = fixture("c-only.txt")


class StandardRequiredTest(GuardrailTestCase):
    SCRIPT = "standard-required.py"
    COLLECT = ["cpp"]

    def build(self, **files):
        return self.workspace(**dict({"CMakeLists.txt": CMAKE, "vcpkg.json": VCPKG}, **files))

    def test_passes_a_build_that_requires_the_standard_it_declares(self):
        self.assert_passed(self.check(self.build()))

    def test_fails_a_build_that_only_prefers_it(self):
        directory = self.build(**{"CMakeLists.txt": PREFERRED})

        violation = self.assert_violation(self.check(directory), "asks for C++20 without requiring it")

        self.assertEqual(violation["evidence"], "CMakeLists.txt")

    def test_fails_a_build_that_turns_the_requirement_off(self):
        directory = self.build(**{"CMakeLists.txt": CMAKE.replace("STANDARD_REQUIRED ON", "STANDARD_REQUIRED OFF")})

        self.assert_violation(self.check(directory), "drops to an older one")

    def test_skips_a_build_that_declares_no_standard_at_all(self):
        directory = self.build(**{"CMakeLists.txt": WITHOUT_STANDARD})

        self.assert_skipped(self.check(directory), "declares no C++ standard for the build to require")

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
        directory = self.workspace(**{"engine/CMakeLists.txt": PREFERRED})

        self.assert_violation(self.check(directory, projectDir="engine"), "asks for C++20 without requiring it")


if __name__ == "__main__":
    unittest.main()
