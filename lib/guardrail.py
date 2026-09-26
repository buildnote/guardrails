import fnmatch
import json
import os
import subprocess
import sys
import time


MISSING = object()

MAX_REPORT_BYTES = 8 * 1024 * 1024

SKIPPED_DIRECTORIES = (".git", "node_modules", "__pycache__", ".gradle", ".terraform", ".venv")

FIXTURE_DIRECTORIES = (
    "fixtures", "__fixtures__", "testdata", "test-fixtures", "testfixtures", "example", "examples",
)


def slashed(path):
    return path.replace(os.sep, "/") if os.sep != "/" else path


def fixture(path):
    segments = path.replace("\\", "/").split("/")

    if any(segment in FIXTURE_DIRECTORIES for segment in segments):
        return True

    return any(
        segments[index] in ("src", "resources", "out") and segments[index + 1] in ("test", "testFixtures")
        for index in range(len(segments) - 1)
    ) or "test-classes" in segments


def modified(path):
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(path)))
    except OSError:
        return None


class GuardrailSkipped(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


class Inputs(object):
    rooted = None

    def input(self, name, default=""):
        value = os.environ.get("GUARDRAIL_INPUT_" + name.upper(), "")
        return value if value else default

    def root(self):
        return os.environ.get("GUARDRAIL_ROOT_DIR", "") or os.getcwd()

    def prefix(self):
        if self.rooted is None:
            root = os.path.realpath(self.root())
            here = os.path.realpath(".")
            self.rooted = slashed(os.path.relpath(here, root)) if here.startswith(root + os.sep) else ""

        return self.rooted

    def path(self, *parts):
        return slashed(os.path.normpath(os.path.join(self.prefix() or ".", *parts)))

    def within(self, stored, *base):
        return slashed(os.path.normpath(os.path.relpath(stored, self.path(*base))))

    def above(self, *names, **options):
        directory = options.get("directory", ".")
        walked = os.path.realpath(directory)
        root = os.path.realpath(self.root())

        while walked != root and walked.startswith(root + os.sep):
            walked = os.path.dirname(walked)
            if any(os.path.exists(os.path.join(walked, name)) for name in names):
                return slashed(os.path.relpath(walked, os.path.realpath(directory)))

        return None

    def log(self, message):
        sys.stderr.write("%s\n" % message)

    def tools(self):
        try:
            return json.loads(os.environ.get("GUARDRAIL_TOOLS", "") or "{}").get("tools") or {}
        except ValueError:
            return {}

    def write(self, result):
        sys.stdout.write(json.dumps(result) + "\n")

    def read(self, path):
        try:
            if os.path.getsize(path) > MAX_REPORT_BYTES:
                self.log("%s is larger than %d bytes and was not read" % (path, MAX_REPORT_BYTES))
                return None

            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except (IOError, OSError):
            return None

    def loaded_facts(self):
        if self.loaded is None:
            path = os.environ.get("GUARDRAIL_FACTS", "")
            try:
                with open(path, encoding="utf-8") as handle:
                    self.loaded = json.load(handle)
            except (IOError, OSError):
                self.loaded = {}
            except ValueError:
                self.unavailable("the collected facts in %s could not be read" % path)

        return self.loaded

    def collected_facts(self, name, default, reason):
        loaded = self.loaded_facts()

        if name in loaded:
            return loaded[name]

        if default is not MISSING:
            return default

        self.unavailable(reason or "no %s facts were collected" % name)

    def optional(self, name, default=None):
        return self.collected_facts(name, default, None)


class Guardrail(Inputs):
    def __init__(self):
        self.violations = []
        self.id = os.environ.get("GUARDRAIL_ID", "")
        self.version = os.environ.get("GUARDRAIL_VERSION", "")
        self.severity = os.environ.get("GUARDRAIL_SEVERITY", "")
        self.loaded = None

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if isinstance(error, GuardrailSkipped):
            self.write({"skip": error.reason})
            sys.exit(0)
        if error is not None:
            return False
        self.write({"violations": self.violations})
        sys.exit(1 if self.violations else 0)

    def violation(self, evidence, message):
        self.violations.append({"evidence": evidence, "message": message})

    def skip(self, reason):
        raise GuardrailSkipped(reason)

    def number(self, name, default):
        raw = self.input(name, str(default))
        try:
            return int(raw)
        except ValueError:
            self.skip("%s '%s' is not a number" % (name, raw))

    def facts(self, name, reason=None):
        collected = self.collected_facts(name, MISSING, reason)

        if isinstance(collected, dict) and "truncated" in collected:
            self.skip(collected["truncated"])

        return collected

    def unavailable(self, reason):
        self.skip(reason)

    def run(self, *command, **options):
        try:
            return subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=options.get("timeout"),
                cwd=options.get("cwd"),
                input=options.get("stdin"),
            )
        except subprocess.TimeoutExpired:
            self.skip("%s timed out" % command[0])
        except OSError:
            self.skip("%s is not available on this runner" % command[0])


class Tool(object):
    def __init__(self, collector, name, path, version, raw):
        self.collector = collector
        self.name = name
        self.path = path
        self.version = version
        self.raw = raw

    def run(self, *args, **options):
        started = time.time()
        result = self.collector.run(*((self.path,) + args), **options)
        self.collector.facts["source"] = "tool"
        self.collector.facts["tool"] = {
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "args": list(args),
            "exitCode": None if result is None else result.returncode,
            "durationMs": int((time.time() - started) * 1000),
        }

        return result


class Collector(Inputs):
    def __init__(self):
        self.facts = {}
        self.loaded = None

    def collected(self, name):
        return self.collected_facts(name, MISSING, None)

    def unavailable(self, reason):
        self.invalid(reason)

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if error is not None:
            return False
        self.write(self.facts)
        sys.exit(0)

    def invalid(self, reason):
        self.log(reason)
        self.facts["incomplete"] = reason
        self.write(self.facts)
        sys.exit(0)

    def nothing(self, reason):
        self.log(reason)
        sys.exit(0)

    def run(self, *command, **options):
        try:
            return subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=options.get("timeout"),
                cwd=options.get("cwd"),
                input=options.get("stdin"),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    def tool(self, name):
        declared = self.tools().get(name)

        if not declared or not declared.get("path"):
            return None

        return Tool(self, name, declared["path"], declared.get("version"), declared.get("raw"))

    def reports(self, *patterns, **options):
        excluded = options.get("exclude") or []
        include_fixtures = options.get("fixtures", False)
        found = []

        for root, directories, names in os.walk("."):
            directories[:] = [it for it in directories if it not in SKIPPED_DIRECTORIES]

            for name in names:
                path = slashed(os.path.relpath(os.path.join(root, name), "."))

                if not any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns):
                    continue

                if any(fnmatch.fnmatch(path, pattern) for pattern in excluded):
                    self.log("%s is excluded" % path)
                    continue

                if not include_fixtures and fixture(path):
                    self.log("%s sits in a test fixture directory and is not a report of this build" % path)
                    continue

                text = self.read(path)

                if text is not None:
                    found.append((path, modified(path), text))

        return sorted(found)

    def sourced(self, source, reports=None):
        self.facts["source"] = source
        self.facts["reports"] = reports or []

    def empty(self, reason):
        self.facts["source"] = "none"
        self.facts["reason"] = reason
        self.facts.setdefault("reports", [])
        self.log(reason)
        self.write(self.facts)
        sys.exit(0)
