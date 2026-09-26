#!/usr/bin/env python3
import argparse
import concurrent.futures
import importlib.util
import io
import os
import subprocess
import sys
import time
import traceback
import unittest
import xml.etree.ElementTree as ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIPPED_DIRECTORIES = {".git", "fixtures", "__pycache__"}


def discover():
    found = []
    for directory, directories, files in os.walk(ROOT):
        directories[:] = sorted(
            it for it in directories
            if it not in SKIPPED_DIRECTORIES and not (directory == ROOT and it == "build")
        )
        found += [
            os.path.relpath(os.path.join(directory, name), ROOT).replace(os.sep, "/")
            for name in sorted(files)
            if name.startswith("test_") and name.endswith(".py")
        ]
    return found


def suite_name(path):
    return path[:-len(".py")].replace("/", ".")


def report_path(output, path):
    return os.path.join(output, "TEST-%s.xml" % suite_name(path))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
        self.started = 0.0

    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def record(self, test, outcome, detail=None):
        self.cases.append((test, outcome, detail, time.monotonic() - self.started))

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "failure", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, "passed")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "failure", "unexpected success")


def write_report(target, name, cases, output, duration):
    suite = ElementTree.Element(
        "testsuite",
        name=name,
        tests=str(len(cases)),
        failures=str(sum(1 for case in cases if case["outcome"] == "failure")),
        errors=str(sum(1 for case in cases if case["outcome"] == "error")),
        skipped=str(sum(1 for case in cases if case["outcome"] == "skipped")),
        time="%.3f" % duration,
    )
    for case in cases:
        element = ElementTree.SubElement(
            suite, "testcase", classname=case["classname"], name=case["name"], time="%.3f" % case["time"]
        )
        if case["outcome"] in ("failure", "error"):
            detail = case["detail"] or ""
            child = ElementTree.SubElement(element, case["outcome"], message=detail.strip().splitlines()[-1] if detail.strip() else "")
            child.text = detail
        elif case["outcome"] == "skipped":
            ElementTree.SubElement(element, "skipped", message=case["detail"] or "")
    ElementTree.SubElement(suite, "system-out").text = output
    os.makedirs(os.path.dirname(target), exist_ok=True)
    ElementTree.ElementTree(suite).write(target, encoding="utf-8", xml_declaration=True)


def run_one(path, target):
    name = suite_name(path)
    stream = io.StringIO()
    started = time.monotonic()
    try:
        spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        tests = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(stream=stream, verbosity=1, resultclass=RecordingResult).run(tests)
    except Exception:
        detail = traceback.format_exc()
        write_report(target, name, [{"classname": name, "name": "load", "outcome": "error", "detail": detail, "time": 0.0}],
                     detail, time.monotonic() - started)
        sys.stdout.write(detail)
        return 1

    cases = [
        {
            "classname": "%s.%s" % (name, type(test).__name__),
            "name": getattr(test, "_testMethodName", str(test)),
            "outcome": outcome,
            "detail": detail,
            "time": duration,
        }
        for test, outcome, detail, duration in result.cases
    ]
    write_report(target, name, cases, stream.getvalue(), time.monotonic() - started)
    sys.stdout.write(stream.getvalue())
    return 0 if result.wasSuccessful() else 1


def run_isolated(path, output):
    target = report_path(output, path)
    completed = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--one", path, "--output", output],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0 and not os.path.exists(target):
        write_report(target, suite_name(path),
                     [{"classname": suite_name(path), "name": "run", "outcome": "error", "detail": completed.stdout, "time": 0.0}],
                     completed.stdout, 0.0)
    return path, completed.returncode, completed.stdout


def main():
    parser = argparse.ArgumentParser(description="Runs every test_*.py and writes a JUnit report per file.")
    parser.add_argument("paths", nargs="*", help="test files to run, relative to the repository root; every one when empty")
    parser.add_argument("--output", default=os.path.join("build", "test-results"), help="directory the JUnit reports are written to")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="test files run at once")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    options = parser.parse_args()
    output = os.path.join(ROOT, options.output)

    if options.one:
        return run_one(options.one, report_path(output, options.one))

    paths = [it.replace(os.sep, "/") for it in options.paths] or discover()
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, options.jobs)) as pool:
        for path, code, printed in pool.map(lambda it: run_isolated(it, output), paths):
            status = "ok" if code == 0 else "FAILED"
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print("::group::%s %s" % (path, status))
                print(printed, end="")
                print("::endgroup::")
            else:
                print("%s %s" % (path, status))
                if code != 0:
                    print(printed, end="")
            if code != 0:
                failed.append(path)

    print("%d test files, %d failed, reports in %s" % (len(paths), len(failed), os.path.relpath(output, ROOT)))
    for path in failed:
        print("::error::%s failed" % path if os.environ.get("GITHUB_ACTIONS") == "true" else "failed: %s" % path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
