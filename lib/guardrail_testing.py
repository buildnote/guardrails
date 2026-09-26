import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

LIBRARY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTORS_DIR = os.path.join(LIBRARY_ROOT, "collectors")
LIB_DIR = os.environ.get("GUARDRAIL_LIB_DIR") or os.path.join(LIBRARY_ROOT, "lib")


class Result(object):
    def __init__(self, payload, code, output):
        self.payload = payload
        self.code = code
        self.output = output

    @property
    def violations(self):
        return (self.payload or {}).get("violations", [])

    @property
    def messages(self):
        return [violation["message"] for violation in self.violations]


class ScriptTestCase(unittest.TestCase):

    bin_dir = None

    root_dir = None

    skipped = False

    def skip(self, reason):
        type(self).skipped = True
        self.skipTest(reason)

    def rooted_at(self, directory):
        self.root_dir = directory
        self.addCleanup(setattr, self, "root_dir", None)

        return directory

    def shim(self, name, version=None, stdout="", stderr="", code=0, responses=None):
        directory = self.shims()
        path = os.path.join(directory, name)
        script = SHIM % {
            "version": json.dumps(version),
            "stdout": json.dumps(stdout),
            "stderr": json.dumps(stderr),
            "code": code,
            "responses": json.dumps(responses or []),
        }

        if os.name == "nt":
            with open(path + ".py", "w", encoding="utf-8", newline="") as handle:
                handle.write(script)

            path = path + ".cmd"
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write('@echo off\r\n"%s" "%%~dp0%s.py" %%*\r\n' % (sys.executable, name))
        else:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(script)

        os.chmod(path, 0o755)

        return path

    def shims(self):
        if self.bin_dir is None:
            self.bin_dir = tempfile.mkdtemp(prefix="buildnote-guardrail-bin")
            self.addCleanup(shutil.rmtree, self.bin_dir, True)
            self.addCleanup(setattr, self, "bin_dir", None)

        return self.bin_dir

    def run_script(self, script, directory, environment):
        completed = subprocess.run(
            [sys.executable, script],
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=environment,
        )

        if completed.returncode == 0 and not completed.stdout.strip():
            return Result(None, completed.returncode, completed.stderr)

        try:
            return Result(json.loads(completed.stdout), completed.returncode, completed.stderr)
        except ValueError:
            self.fail("%s printed no result: %s%s" % (script, completed.stdout, completed.stderr))

    def environment(self, inputs):
        environment = dict(
            os.environ,
            PYTHONPATH=LIB_DIR,
            PYTHONDONTWRITEBYTECODE="1",
            **dict(("GUARDRAIL_INPUT_%s" % name.upper(), str(value)) for name, value in inputs.items())
        )

        if self.bin_dir is not None:
            environment["PATH"] = self.bin_dir + os.pathsep + environment.get("PATH", "")

        if self.root_dir is not None:
            environment["GUARDRAIL_ROOT_DIR"] = self.root_dir

        return environment

    def resolved_tools(self, name, environment):
        resolved = {}
        available = self.bin_dir or ""

        for tool, declaration in collector(name).get("tools", {}).items():
            path = which(tool, available)

            if path is None:
                resolved[tool] = {"path": None, "version": None, "raw": None}
                continue

            raw = probe(path, declaration.get("version", []), environment)
            resolved[tool] = {
                "path": path,
                "version": None if raw is None else version_in(raw),
                "raw": raw,
                "minVersion": declaration.get("minVersion"),
            }

        return json.dumps({"tools": resolved})

    def workspace(self, **files):
        directory = tempfile.mkdtemp(prefix="buildnote-guardrail")
        self.addCleanup(shutil.rmtree, directory, True)

        for name, text in files.items():
            self.write(directory, name, text)

        return directory

    def write(self, directory, name, text):
        path = os.path.join(directory, name)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

        return path

    def facts_file(self, facts):
        directory = tempfile.mkdtemp(prefix="buildnote-guardrail-facts")
        self.addCleanup(shutil.rmtree, directory, True)

        return self.write(directory, "facts.json", json.dumps(facts))

    def collect_into(self, facts, directory, name, inputs):
        if name in facts:
            return

        collects = collector(name).get("collect", [])
        for dependency in collects:
            self.collect_into(facts, directory, dependency, inputs)

        environment = self.environment(declared(name, inputs))
        environment["GUARDRAIL_TOOLS"] = self.resolved_tools(name, environment)
        if collects:
            environment["GUARDRAIL_FACTS"] = self.facts_file(
                dict((it, facts[it]) for it in collects if it in facts)
            )

        result = self.run_script(collector_script(name), directory, environment)

        self.assertEqual(result.code, 0, result.output)
        if result.payload is None:
            return

        self.assert_declared(name, result.payload)

        facts[name] = result.payload

    def assert_declared(self, name, facts):
        declared = list(collector(name).get("facts", {}))
        collected = []
        for fact, value in facts.items():
            if fact != INCOMPLETE:
                collected += paths_in(value, fact, declared)

        undeclared = [fact for fact in collected if not describes(declared, fact)]

        self.assertEqual(undeclared, [], "%s collects facts its definition does not declare" % name)

        seen(name).update(fact for fact in collected if fact in declared)

    def collected(self, directory, names, inputs):
        facts = {}
        for name in names:
            self.collect_into(facts, directory, name, inputs)

        return facts

    def repository(self, *messages):
        directory = self.workspace()

        self.git(directory, "init", "--quiet")
        self.git(directory, "config", "user.email", "guardrails@buildnote.io")
        self.git(directory, "config", "user.name", "Guardrails")
        self.git(directory, "config", "commit.gpgsign", "false")
        for message in ("chore: base",) + messages:
            self.commit(directory, message)

        return directory

    def commit(self, directory, message):
        self.git(directory, "commit", "--quiet", "--allow-empty", "-m", message)

        return self.git(directory, "rev-parse", "HEAD").strip()

    def head(self, directory):
        return self.git(directory, "rev-parse", "HEAD").strip()

    def git(self, directory, *command):
        completed = subprocess.run(
            ("git",) + command,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if completed.returncode != 0:
            self.fail("git %s failed: %s" % (command[0], completed.stderr.strip()))

        return completed.stdout


class CollectorTestCase(ScriptTestCase):
    COLLECTOR = None

    @classmethod
    def setUpClass(cls):
        cls.expected = len([name for name in dir(cls) if name.startswith("test")])
        cls.ran = 0
        cls.skipped = False
        seen(cls.COLLECTOR).clear()

    @classmethod
    def tearDownClass(cls):
        if cls.ran != cls.expected or cls.skipped:
            return

        undocumented = [
            fact for fact in collector(cls.COLLECTOR).get("facts", {})
            if fact not in seen(cls.COLLECTOR)
        ]
        if undocumented:
            raise AssertionError(
                "%s declares facts no test collects: %s" % (cls.COLLECTOR, ", ".join(undocumented))
            )

    def tearDown(self):
        type(self).ran += 1

    def collect(self, directory, **inputs):
        return self.collected(directory, [self.COLLECTOR], inputs).get(self.COLLECTOR)


class GuardrailTestCase(ScriptTestCase):
    SCRIPT = None
    COLLECT = []

    def check(self, directory, **inputs):
        environment = self.environment(inputs)
        facts = self.facts(directory, inputs)
        if facts is not None:
            environment["GUARDRAIL_FACTS"] = facts

        return self.run_script(self.script(), directory, environment)

    def facts(self, directory, inputs):
        if not self.COLLECT:
            return None

        collected = self.collected(directory, self.COLLECT, inputs)

        return self.facts_file(dict((name, collected[name]) for name in self.COLLECT if name in collected))

    def assert_passed(self, result):
        self.assertEqual(result.payload, {"violations": []}, result.output)
        self.assertEqual(result.code, 0)

    def assert_skipped(self, result, reason):
        self.assertIn("skip", result.payload)
        self.assertIn(reason, result.payload["skip"])
        self.assertNotIn("violations", result.payload)
        self.assertEqual(result.code, 0)

    def assert_violation(self, result, message):
        self.assertEqual(len(result.violations), 1, result.payload)
        self.assertIn(message, result.violations[0]["message"])
        self.assertEqual(result.code, 1)

        return result.violations[0]

    def script(self):
        module = sys.modules[type(self).__module__]

        return os.path.join(os.path.dirname(os.path.abspath(module.__file__)), self.SCRIPT)


INCOMPLETE = "incomplete"

VERSION_NUMBER = re.compile(r"\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.\-]+)?")

SHIM = """#!/usr/bin/env python3
import sys

VERSION = %(version)s
RESPONSES = %(responses)s

arguments = " ".join(sys.argv[1:])

if VERSION is not None and ("--version" in sys.argv or "version" in sys.argv or "-v" in sys.argv):
    sys.stdout.write(VERSION + "\\n")
    sys.exit(0)

for match, out, err, code in RESPONSES:
    if match in arguments:
        sys.stdout.write(out)
        sys.stderr.write(err)
        sys.exit(code)

sys.stdout.write(%(stdout)s)
sys.stderr.write(%(stderr)s)
sys.exit(%(code)d)
"""


WINDOWS_EXTENSIONS = ("", ".cmd", ".bat", ".exe")


def fixtures(test_file):
    directory = os.path.join(os.path.dirname(os.path.abspath(test_file)), "fixtures")

    def fixture(name):
        with open(os.path.join(directory, name), encoding="utf-8", newline="") as handle:
            return handle.read()

    return fixture


def slashed(path):
    return path.replace(os.sep, "/") if os.sep != "/" else path


def unreadable_is_enforced():
    # Windows carries no mode bit that stops this process reading its own file, and root ignores the one POSIX has.
    return os.name != "nt" and getattr(os, "geteuid", lambda: 1)() != 0


def which(name, path):
    extensions = WINDOWS_EXTENSIONS if os.name == "nt" else ("",)

    for directory in path.split(os.pathsep):
        for extension in extensions:
            candidate = os.path.join(directory, name + extension)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

    return None


def probe(path, arguments, environment):
    if not arguments:
        return None

    completed = subprocess.run(
        [path] + list(arguments),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=environment,
    )

    output = completed.stdout.strip() or completed.stderr.strip()

    return output.splitlines()[0].strip() if output else None


def version_in(raw):
    found = VERSION_NUMBER.search(raw)

    return found.group(0) if found else None

COLLECTED = {}


def seen(name):
    return COLLECTED.setdefault(name, set())


def describes(declared, fact):
    return fact in declared or any(path.startswith(fact + ".") for path in declared)


def paths_in(value, prefix, declared):
    found = [prefix]

    if isinstance(value, dict):
        keyed = prefix + "[path]"
        if any(path.startswith(keyed + ".") for path in declared):
            for nested in value.values():
                found += paths_in(nested, keyed, declared)
        elif any(path.startswith(prefix + ".") for path in declared):
            for name, nested in value.items():
                found += paths_in(nested, prefix + "." + name, declared)
    elif isinstance(value, list) and any(path.startswith(prefix + "[].") for path in declared):
        for nested in value:
            found += paths_in(nested, prefix + "[]", declared)

    return found


def collector(name):
    with open(os.path.join(COLLECTORS_DIR, name, "collector.json"), encoding="utf-8") as handle:
        return json.load(handle)


def collector_script(name):
    return os.path.join(COLLECTORS_DIR, name, collector(name)["run"])


def declared(name, inputs):
    accepted = collector(name).get("inputs", {})

    return dict(
        (input, inputs.get(input, declaration.get("default", "")))
        for input, declaration in accepted.items()
    )
