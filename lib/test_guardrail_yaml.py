#!/usr/bin/env python3
import os, sys
LIB = os.environ.get("GUARDRAIL_LIB_DIR") or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LIB)

import re
import unittest

from guardrail_yaml import documents, parse, unsupported

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

REASON = re.compile(r"^[a-z][a-z -]+ at line [0-9]+$")

REJECTED = (
    ("anchor", "jobs:\n  build:\n    steps: &shared\n      - run: make\n", "anchor at line 3"),
    ("alias", "jobs:\n  build:\n    steps: *shared\n", "alias at line 3"),
    ("merge key", "defaults:\n  a: 1\nbuild:\n  <<: *defaults\n", "merge key at line 4"),
    ("shorthand tag", "name: Build\nversion: !!str 25\n", "tag at line 2"),
    ("application tag", "bucket:\n  name: !Ref BucketName\n", "tag at line 2"),
    ("tab indentation", "jobs:\n\tbuild:\n\t\truns-on: ubuntu-latest\n", "tab indentation at line 2"),
    ("non-space indentation", "jobs:\n\xa0\xa0build: x\n", "non-space indentation at line 2"),
    ("complex key", "? - a\n  - b\n: value\n", "complex key at line 1"),
    ("multi-line flow", "on:\n  push:\n    branches: [\n      main,\n    ]\n", "multi-line flow collection at line 3"),
    ("nested flow sequence", "matrix: [[1, 2], 3]\n", "nested flow collection at line 1"),
    ("nested flow mapping", "matrix: {os: [linux]}\n", "nested flow collection at line 1"),
    ("inconsistent indent", "jobs:\n    build:\n  test:\n", "unexpected indentation at line 3"),
    ("negative dedent", "  name: Build\njobs: {}\n", "unexpected indentation at line 2"),
    ("indented continuation", "name: Build\n  and test\n", "unexpected indentation at line 2"),
    ("unterminated quote", "name: 'Build\n", "unterminated quote at line 1"),
    ("unsupported escape", 'name: "Build \\q"\n', "unsupported escape at line 1"),
    ("multiple documents", "kind: Deployment\n---\nkind: Service\n", "multiple documents at line 2"),
)

ACCEPTED = (
    "on: push\n",
    "on:\n  push:\n    branches:\n      - main\n",
    '"on": push\n',
    "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          fetch-depth: 0\n",
    "steps:\n- run: make\n- run: make test\n",
    "matrix: [linux, macos]\nlimits: {cpu: 2, memory: '1Gi'}\n",
    "run: |\n  echo one\n  echo two\n",
    "note: >-\n  one\n  two\n",
    "empty:\nnothing: ~\nnulled: null\n",
    "",
    "# only a comment\n",
)


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


def workflow(name):
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as handle:
        return handle.read()


def workflow_names():
    return sorted(name for name in os.listdir(WORKFLOWS) if name.endswith(".yml") or name.endswith(".yaml"))


class ScalarTest(unittest.TestCase):
    def test_reads_plain_strings(self):
        self.assertEqual(parse("name: Build Backend\n"), {"name": "Build Backend"})

    def test_reads_integers_and_floats(self):
        self.assertEqual(parse("timeout: 15\nratio: 0.5\nnegative: -3\n"), {"timeout": 15, "ratio": 0.5, "negative": -3})

    def test_reads_booleans_in_every_spelling(self):
        parsed = parse("a: true\nb: False\nc: yes\nd: NO\ne: on\nf: off\n")

        self.assertEqual(parsed, {"a": True, "b": False, "c": True, "d": False, "e": True, "f": False})

    def test_reads_nulls(self):
        self.assertEqual(parse("a:\nb: ~\nc: null\nd: NULL\n"), {"a": None, "b": None, "c": None, "d": None})

    def test_never_coerces_a_quoted_scalar(self):
        parsed = parse("version: '25'\nenabled: \"true\"\nempty: ''\nnothing: \"~\"\n")

        self.assertEqual(parsed, {"version": "25", "enabled": "true", "empty": "", "nothing": "~"})

    def test_keeps_a_version_like_scalar_a_string(self):
        self.assertEqual(parse("version: 1.2.3\nimage: nginx:1.25\n"), {"version": "1.2.3", "image": "nginx:1.25"})

    def test_keeps_a_number_the_yaml_versions_disagree_about_verbatim(self):
        parsed = parse("mode: 0644\nmask: 0x1f\nwhen: 1:30\nleading: 08\n")

        self.assertEqual(parsed, {"mode": "0644", "mask": "0x1f", "when": "1:30", "leading": "08"})

    def test_reads_double_quoted_escapes(self):
        self.assertEqual(parse('a: "one\\ntwo\\tthree \\"quoted\\" \\\\"\n'), {"a": 'one\ntwo\tthree "quoted" \\'})

    def test_reads_a_doubled_single_quote(self):
        self.assertEqual(parse("a: 'it''s here'\n"), {"a": "it's here"})

    def test_drops_a_comment_at_the_end_of_a_line(self):
        self.assertEqual(parse("a: 1 # counted\nb: 2\n"), {"a": 1, "b": 2})

    def test_keeps_a_hash_that_is_not_a_comment(self):
        parsed = parse("a: '# hash'\nb: https://buildnote.io/x#y\n")

        self.assertEqual(parsed, {"a": "# hash", "b": "https://buildnote.io/x#y"})

    def test_reads_a_value_with_a_comment_and_nothing_else_as_null(self):
        self.assertEqual(parse("dev: # released to the dev channel only\n"), {"dev": None})

    def test_keeps_an_apostrophe_in_a_plain_scalar(self):
        self.assertEqual(parse("a: don't stop # here\n"), {"a": "don't stop"})

    def test_reads_a_plain_scalar_on_the_line_below_its_key(self):
        parsed = parse("steps:\n  run:\n    buildnote --verbose collect --timeout 30\n  if: always()\n")

        self.assertEqual(parsed, {"steps": {"run": "buildnote --verbose collect --timeout 30", "if": "always()"}})


class StructureTest(unittest.TestCase):
    def test_nests_mappings_by_indentation(self):
        parsed = parse("on:\n  push:\n    branches:\n      - main\n")

        self.assertEqual(parsed, {"on": {"push": {"branches": ["main"]}}})

    def test_reads_a_sequence_of_mappings(self):
        parsed = parse("steps:\n  - name: Checkout\n    uses: actions/checkout@v4\n  - name: Build\n    run: make\n")

        self.assertEqual(parsed, {"steps": [
            {"name": "Checkout", "uses": "actions/checkout@v4"},
            {"name": "Build", "run": "make"},
        ]})

    def test_reads_a_sequence_indented_level_with_its_key(self):
        self.assertEqual(parse("branches:\n- main\n- release\nname: x\n"), {"branches": ["main", "release"], "name": "x"})

    def test_reads_an_empty_sequence_item(self):
        self.assertEqual(parse("a:\n  -\n  - two\n"), {"a": [None, "two"]})

    def test_reads_a_nested_sequence(self):
        self.assertEqual(parse("a:\n  - - one\n    - two\n"), {"a": [["one", "two"]]})

    def test_reads_a_top_level_sequence(self):
        self.assertEqual(parse("- one\n- two\n"), ["one", "two"])

    def test_reads_flow_collections(self):
        parsed = parse("branches: [main, 'release/*']\nlimits: {cpu: 2, memory: '256Mi'}\n")

        self.assertEqual(parsed, {"branches": ["main", "release/*"], "limits": {"cpu": 2, "memory": "256Mi"}})

    def test_reads_empty_flow_collections(self):
        self.assertEqual(parse("a: []\nb: {}\n"), {"a": [], "b": {}})

    def test_reads_a_flow_scalar_holding_a_comma(self):
        self.assertEqual(parse("a: ['one, two', three]\n"), {"a": ["one, two", "three"]})

    def test_reads_keys_holding_dots_slashes_and_dashes(self):
        parsed = parse("app.kubernetes.io/name: web\nif-no-files-found: warn\n")

        self.assertEqual(parsed, {"app.kubernetes.io/name": "web", "if-no-files-found": "warn"})

    def test_reads_an_empty_value_as_null(self):
        self.assertEqual(parse("on:\n  pull_request:\n  workflow_dispatch:\n"), {"on": {"pull_request": None, "workflow_dispatch": None}})

    def test_ignores_comment_lines_at_any_indentation(self):
        parsed = parse("with:\n#          version: 'dev'\n          installOnly: 'true'\n")

        self.assertEqual(parsed, {"with": {"installOnly": "true"}})

    def test_reads_a_file_that_starts_with_a_byte_order_mark(self):
        parsed = parse("\ufeffname: Build\non: push\n")

        self.assertEqual(parsed, {"name": "Build", "on": "push"})
        self.assertIsNone(unsupported("\ufeffname: Build\non: push\n"))

    def test_reads_windows_line_endings(self):
        self.assertEqual(parse("a: 1\r\nb: 2\r\n"), {"a": 1, "b": 2})


class BlockScalarTest(unittest.TestCase):
    def test_a_literal_keeps_its_newlines(self):
        self.assertEqual(parse("run: |\n  one\n  two\n"), {"run": "one\ntwo\n"})

    def test_a_folded_joins_its_lines(self):
        self.assertEqual(parse("run: >\n  one\n  two\n"), {"run": "one two\n"})

    def test_a_folded_keeps_a_blank_line_as_a_newline(self):
        self.assertEqual(parse("run: >\n  one\n\n  two\n"), {"run": "one\ntwo\n"})

    def test_a_folded_keeps_an_indented_line_literally(self):
        self.assertEqual(parse("run: >\n  one\n    two\n  three\n"), {"run": "one\n  two\nthree\n"})

    def test_stripping_removes_the_trailing_newline(self):
        self.assertEqual(parse("run: |-\n  one\n  two\n"), {"run": "one\ntwo"})
        self.assertEqual(parse("run: >-\n  one\n  two\n"), {"run": "one two"})

    def test_keeping_keeps_every_trailing_newline(self):
        self.assertEqual(parse("run: |+\n  one\n\n\n"), {"run": "one\n\n\n"})

    def test_clipping_keeps_one_trailing_newline(self):
        self.assertEqual(parse("run: |\n  one\n\n\nnext: 1\n"), {"run": "one\n", "next": 1})

    def test_a_body_holding_a_hash_and_a_colon_survives_verbatim(self):
        text = "steps:\n  - run: |\n      # Both work:\n      echo \"Job name is $GITHUB_JOB\"\n      key: value # not a comment\n    if: always()\n"

        parsed = parse(text)

        self.assertEqual(parsed["steps"][0]["run"], "# Both work:\necho \"Job name is $GITHUB_JOB\"\nkey: value # not a comment\n")
        self.assertTrue(parsed["steps"][0]["if"])

    def test_a_body_holding_yaml_constructs_is_not_parsed_as_yaml(self):
        text = "run: |\n  gh release view x >/dev/null 2>&1\n  native-image \"-H:+ReportExceptionStackTraces\"\n  echo '&anchor !tag ---'\n"

        self.assertEqual(parse(text), {"run": "gh release view x >/dev/null 2>&1\nnative-image \"-H:+ReportExceptionStackTraces\"\necho '&anchor !tag ---'\n"})

    def test_a_blank_line_does_not_end_a_body(self):
        self.assertEqual(parse("run: |\n  one\n\n  two\nnext: 1\n"), {"run": "one\n\ntwo\n", "next": 1})

    def test_a_body_ending_the_file_without_a_newline_keeps_no_newline(self):
        self.assertEqual(parse("run: |\n  one"), {"run": "one"})

    def test_a_whitespace_only_line_keeps_its_place_in_a_body(self):
        self.assertEqual(parse("run: |\n  one\n   \n  two\n"), {"run": "one\n \ntwo\n"})

    def test_an_empty_body_reads_as_an_empty_string(self):
        self.assertEqual(parse("run: |\nnext: 1\n"), {"run": "", "next": 1})


class ActionsOnKeyTest(unittest.TestCase):
    def test_a_plain_on_key_stays_a_string(self):
        parsed = parse("on: push\n")

        self.assertEqual(list(parsed), ["on"])
        self.assertEqual(parsed["on"], "push")

    def test_a_block_on_key_stays_a_string(self):
        parsed = parse("on:\n  push:\n    branches: [main]\n")

        self.assertEqual(list(parsed), ["on"])
        self.assertEqual(parsed["on"], {"push": {"branches": ["main"]}})

    def test_a_quoted_on_key_stays_a_string(self):
        parsed = parse('"on": push\n')

        self.assertEqual(list(parsed), ["on"])
        self.assertEqual(parsed["on"], "push")

    def test_no_key_is_ever_coerced(self):
        parsed = parse("on: push\nyes: 1\nno: 2\noff: 3\n")

        self.assertEqual(list(parsed), ["on", "yes", "no", "off"])
        self.assertNotIn(True, parsed)
        self.assertNotIn(False, parsed)

    def test_a_boolean_value_is_still_coerced(self):
        self.assertEqual(parse("with:\n  verbose: true\n"), {"with": {"verbose": True}})


class RejectionTest(unittest.TestCase):
    def test_names_the_construct_and_the_line(self):
        for name, text, reason in REJECTED:
            self.assertEqual(unsupported(text), reason, name)

    def test_reports_nothing_parsed_for_every_rejection(self):
        for name, text, reason in REJECTED:
            self.assertIsNone(parse(text), name)

    def test_every_reason_reads_as_a_construct_and_a_line(self):
        for name, text, reason in REJECTED:
            self.assertRegex(reason, REASON, name)

    def test_accepts_what_it_can_represent(self):
        for text in ACCEPTED:
            self.assertIsNone(unsupported(text), repr(text))

    def test_an_anchor_inside_a_block_scalar_is_not_a_rejection(self):
        self.assertEqual(parse("run: |\n  &anchor\n"), {"run": "&anchor\n"})

    def test_a_document_of_only_comments_reads_as_null(self):
        self.assertIsNone(parse("# nothing here\n"))
        self.assertIsNone(unsupported("# nothing here\n"))

    def test_reports_a_reason_rather_than_raising_on_anything(self):
        for text in ("a: [", "{", "a:\n  - b: [", "a: 'b\nc: \"d", "a: \"b", "a: [1, [2]]"):
            self.assertIsNone(parse(text), repr(text))
            self.assertIsNotNone(unsupported(text), repr(text))


class DocumentsTest(unittest.TestCase):
    def test_splits_on_a_document_marker(self):
        self.assertEqual(documents("kind: Deployment\n---\nkind: Service\n"), [{"kind": "Deployment"}, {"kind": "Service"}])

    def test_a_leading_marker_is_one_document(self):
        self.assertEqual(documents("---\nkind: Deployment\n"), [{"kind": "Deployment"}])
        self.assertIsNone(unsupported("---\nkind: Deployment\n"))

    def test_a_trailing_marker_is_one_document(self):
        self.assertEqual(documents("kind: Deployment\n---\n"), [{"kind": "Deployment"}])

    def test_a_directive_is_not_a_document_of_its_own(self):
        self.assertEqual(documents("%YAML 1.2\n---\nkind: Deployment\n"), [{"kind": "Deployment"}])
        self.assertEqual(parse("%YAML 1.2\n---\nkind: Deployment\n"), {"kind": "Deployment"})

    def test_a_document_end_marker_closes_a_document(self):
        self.assertEqual(documents("kind: Deployment\n...\n"), [{"kind": "Deployment"}])

    def test_a_document_outside_the_subset_becomes_none(self):
        parsed = documents("kind: Deployment\n---\nkind: !Ref Service\n---\nkind: Ingress\n")

        self.assertEqual(parsed, [{"kind": "Deployment"}, None, {"kind": "Ingress"}])

    def test_parse_refuses_more_than_one_document(self):
        text = "kind: Deployment\n---\nkind: Service\n"

        self.assertIsNone(parse(text))
        self.assertEqual(unsupported(text), "multiple documents at line 2")

    def test_reads_a_kubernetes_manifest(self):
        parsed = documents(fixture("yaml_kubernetes.yml"))

        self.assertEqual([document["kind"] for document in parsed], ["Deployment", "Service"])
        container = parsed[0]["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["command"], ["nginx", "-g", "daemon off;"])
        self.assertEqual(container["ports"], [{"containerPort": 8080}])
        self.assertEqual(container["resources"]["limits"], {"cpu": "500m", "memory": "256Mi"})
        self.assertTrue(parsed[0]["spec"]["template"]["spec"]["securityContext"]["runAsNonRoot"])

    def test_reads_a_compose_file(self):
        parsed = parse(fixture("yaml_compose.yml"))

        service = parsed["services"]["clickhouse"]
        self.assertEqual(service["ports"], ["8123:8123", "9000:9000"])
        self.assertEqual(service["environment"], {"CLICKHOUSE_DB": "buildnote", "CLICKHOUSE_PASSWORD": ""})
        self.assertEqual(service["healthcheck"]["test"], ["CMD", "wget", "--spider", "-q", "localhost:8123/ping"])
        self.assertEqual(service["command"], "--config-file=/etc/clickhouse-server/config.xml --log-level=warning\n")
        self.assertEqual(service["deploy"]["resources"]["limits"]["cpus"], "0.50")
        self.assertEqual(parsed["volumes"], {"data": {}})


class WorkflowTest(unittest.TestCase):
    def test_finds_the_workflows_of_this_repository(self):
        self.assertTrue(workflow_names())

    def test_parses_every_workflow_of_this_repository(self):
        for name in workflow_names():
            text = workflow(name)

            self.assertIsNone(unsupported(text), name)
            self.assertIsNotNone(parse(text), name)

    def test_every_workflow_keeps_on_as_a_string_key(self):
        for name in workflow_names():
            parsed = parse(workflow(name))

            self.assertIn("on", parsed, name)
            self.assertNotIn(True, parsed, name)

    def test_every_workflow_describes_its_jobs_as_mappings(self):
        for name in workflow_names():
            jobs = parse(workflow(name))["jobs"]

            self.assertIsInstance(jobs, dict, name)
            self.assertTrue(jobs, name)
            for job, described in jobs.items():
                self.assertIsInstance(described, dict, "%s %s" % (name, job))

    def test_every_workflow_step_is_a_mapping(self):
        for name in workflow_names():
            for job, described in parse(workflow(name))["jobs"].items():
                for step in described.get("steps", []):
                    self.assertIsInstance(step, dict, "%s %s" % (name, job))
                    self.assertTrue(set(step) & {"run", "uses", "name"}, "%s %s" % (name, job))


if __name__ == "__main__":
    unittest.main()
