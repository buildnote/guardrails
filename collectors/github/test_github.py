#!/usr/bin/env python3
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, LIBRARY_ROOT, fixtures

fixture = fixtures(__file__)

OWN_WORKFLOWS = os.path.join(LIBRARY_ROOT, ".github", "workflows")

SHA = "1e204e9a9253d643386038d443f96446fa156a97"

BUILD = fixture("build.yml") % SHA

PINS = fixture("pins.yml") % SHA

RUNNERS = fixture("runners.yml")

BARE = fixture("bare.yml")

EMPTY_PERMISSIONS = fixture("empty-permissions.yml")

TRIAGE = fixture("triage.yml")

LITERAL = "hunter2-must-not-appear"

DEPLOY = fixture("deploy.yml") % (LITERAL, LITERAL)

CALLS = fixture("calls.yml")

ANCHORED = fixture("anchored.yml")


OWNERS = fixture("owners.CODEOWNERS")

SCOPED = """/docs/ @company/docs
"""

MALFORMED = """docs/ platform-team
/src/ @company/platform
"""

BRACKETED = """* @company/platform
[Documentation]
"""

def at(name, text):
    return {".github/workflows/%s" % name: text}


class GitHubTest(CollectorTestCase):
    COLLECTOR = "github"

    def owned(self, paths, codeowners=OWNERS, location="CODEOWNERS"):
        workspace = self.workspace(**{location: codeowners, "README.md": "# Widget\n"})

        return self.collect(workspace, paths=paths)["codeowners"]

    def test_reads_a_workflow(self):
        facts = self.collect(self.workspace(**at("build.yml", BUILD)))
        workflow = facts["workflows"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(workflow["path"], ".github/workflows/build.yml")
        self.assertEqual(workflow["name"], "Build")
        self.assertEqual(workflow["triggers"], ["push", "workflow_dispatch"])
        self.assertEqual(facts["triggers"], ["push", "workflow_dispatch"])
        self.assertEqual(workflow["defaults"], {"run": {"shell": "bash"}})
        self.assertTrue(workflow["concurrency"])
        self.assertEqual(facts["untrustedTriggers"], [])
        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["counts"], {"workflows": 1, "jobs": 2, "steps": 3})

    def test_names_the_workflow_it_read(self):
        facts = self.collect(self.workspace(**at("build.yml", BUILD)))
        report = facts["reports"][0]

        self.assertEqual(report["path"], ".github/workflows/build.yml")
        self.assertEqual(report["format"], "workflow")
        self.assertIsNotNone(report["modified"])

    def test_reads_a_job(self):
        facts = self.collect(self.workspace(**at("build.yml", BUILD)))
        build, deploy = facts["workflows"][0]["jobs"]

        self.assertEqual(build["id"], "build")
        self.assertEqual(build["name"], "Build the widget")
        self.assertEqual(build["runsOn"], "ubuntu-latest")
        self.assertEqual(build["environment"], "staging")
        self.assertEqual(build["needs"], [])
        self.assertIsNone(build["if"])
        self.assertIsNone(build["uses"])
        self.assertEqual(deploy["needs"], ["build"])
        self.assertEqual(deploy["if"], "github.ref == 'refs/heads/main'")
        self.assertEqual(deploy["uses"], "./.github/workflows/deploy.yml")
        self.assertEqual(deploy["steps"], [])

    def test_reads_a_step(self):
        facts = self.collect(self.workspace(**at("build.yml", BUILD)))
        checkout, java, build = facts["workflows"][0]["jobs"][0]["steps"]

        self.assertEqual(checkout["name"], "Check out")
        self.assertEqual(java["withKeys"], ["distribution", "java-version"])
        self.assertEqual(build["run"], "./gradlew check")
        self.assertEqual(build["shell"], "bash")
        self.assertIsNone(build["uses"])
        self.assertIsNone(java["shell"])

    def test_pins_an_action_only_when_the_ref_is_a_sha(self):
        facts = self.collect(self.workspace(**at("pins.yml", PINS)))
        steps = facts["workflows"][0]["jobs"][0]["steps"]

        self.assertEqual([step["ref"] for step in steps], [SHA, "v4.0.2", "main", None, None])
        self.assertEqual([step["pinned"] for step in steps], [True, False, False, False, False])
        self.assertEqual(steps[0]["action"], "actions/checkout")
        self.assertEqual(steps[0]["uses"], "actions/checkout@%s" % SHA)
        self.assertEqual(steps[1]["action"], "actions/setup-node")
        self.assertEqual(steps[2]["action"], "some-org/some-action")

    def test_tells_a_local_action_from_a_docker_one(self):
        facts = self.collect(self.workspace(**at("pins.yml", PINS)))
        local, docker = facts["workflows"][0]["jobs"][0]["steps"][3:]

        self.assertEqual(local["action"], "./.github/actions/setup")
        self.assertTrue(local["local"])
        self.assertFalse(local["docker"])
        self.assertEqual(docker["action"], "alpine:3.19")
        self.assertTrue(docker["docker"])
        self.assertFalse(docker["local"])

    def test_reads_permissions_at_both_levels(self):
        facts = self.collect(self.workspace(**at("build.yml", BUILD)))
        workflow = facts["workflows"][0]

        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(workflow["jobs"][0]["permissions"], {"contents": "read", "id-token": "write"})

    def test_tells_undeclared_permissions_from_declared_empty_ones(self):
        undeclared = self.collect(self.workspace(**at("bare.yml", BARE)))["workflows"][0]
        empty = self.collect(self.workspace(**at("empty.yml", EMPTY_PERMISSIONS)))["workflows"][0]

        self.assertIsNone(undeclared["permissions"])
        self.assertIsNone(undeclared["jobs"][0]["permissions"])
        self.assertEqual(empty["permissions"], {})
        self.assertEqual(empty["jobs"][0]["permissions"], {})

    def test_tells_a_hosted_runner_from_a_self_hosted_one(self):
        facts = self.collect(self.workspace(**at("runners.yml", RUNNERS)))
        hosted, fleet, custom, chosen = facts["workflows"][0]["jobs"]

        self.assertFalse(hosted["selfHosted"])
        self.assertEqual(fleet["runsOn"], ["self-hosted", "linux", "x64"])
        self.assertTrue(fleet["selfHosted"])
        self.assertTrue(custom["selfHosted"])
        self.assertIsNone(chosen["selfHosted"])

    def test_records_a_timeout_and_its_absence(self):
        facts = self.collect(self.workspace(**at("runners.yml", RUNNERS)))
        hosted, fleet = facts["workflows"][0]["jobs"][:2]
        build = self.collect(self.workspace(**at("build.yml", BUILD)))["workflows"][0]["jobs"][0]

        self.assertIsNone(hosted["timeoutMinutes"])
        self.assertEqual(fleet["timeoutMinutes"], 5)
        self.assertEqual(build["timeoutMinutes"], 20)

    def test_records_an_untrusted_trigger(self):
        facts = self.collect(self.workspace(**at("triage.yml", TRIAGE)))

        self.assertEqual(facts["untrustedTriggers"], [
            {"path": ".github/workflows/triage.yml", "trigger": "pull_request_target"},
            {"path": ".github/workflows/triage.yml", "trigger": "issue_comment"},
            {"path": ".github/workflows/triage.yml", "trigger": "workflow_run"},
        ])

    def test_collects_every_interpolation_in_a_run_body(self):
        facts = self.collect(self.workspace(**at("triage.yml", TRIAGE)))
        step = facts["workflows"][0]["jobs"][0]["steps"][0]

        self.assertEqual(step["interpolations"], [
            "github.event.pull_request.title",
            "github.event.comment.body",
        ])

    def test_collects_secret_names_and_no_secret_values(self):
        facts = self.collect(self.workspace(**at("deploy.yml", DEPLOY)))
        job = facts["workflows"][0]["jobs"][0]

        self.assertEqual(job["secretsUsed"], ["DEPLOY_TOKEN", "API_KEY"])
        self.assertEqual(job["steps"][2]["run"], "rm -f ./load_secrets.sh config/secrets.yml")
        self.assertEqual(job["steps"][0]["withKeys"], ["username", "password"])
        self.assertNotIn(LITERAL, json.dumps(facts))

    def test_collects_the_secrets_a_reusable_workflow_call_passes_on(self):
        facts = self.collect(self.workspace(**at("calls.yml", CALLS)))
        job = facts["workflows"][0]["jobs"][0]

        self.assertEqual(job["secretsUsed"], ["NPM_TOKEN"])

    def test_truncates_a_long_run_body_but_reads_the_whole_of_it_first(self):
        body = "\n".join(["echo %d" % number for number in range(400)] + ["echo ${{ github.event.issue.title }}"])
        workflow = BARE.replace("      - run: make", "      - run: |\n          " + body.replace("\n", "\n          "))
        facts = self.collect(self.workspace(**at("long.yml", workflow)))
        step = facts["workflows"][0]["jobs"][0]["steps"][0]

        self.assertGreater(len(body), 2000)
        self.assertEqual(len(step["run"]), 2000)
        self.assertEqual(step["interpolations"], ["github.event.issue.title"])

    def test_reads_nothing_outside_the_workflows_directory(self):
        facts = self.collect(self.workspace(**{"build.yml": BUILD, ".gitlab-ci.yml": "build:\n  script:\n    - make\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertEqual(facts["reports"], [])

    def test_records_a_workflow_outside_the_yaml_subset_rather_than_guessing_at_it(self):
        workspace = self.workspace(**dict(at("anchored.yml", ANCHORED), **at("build.yml", BUILD)))

        facts = self.collect(workspace)

        self.assertEqual(facts["unparsed"], [{
            "path": ".github/workflows/anchored.yml",
            "reason": "anchor at line 3",
        }])
        self.assertEqual([workflow["path"] for workflow in facts["workflows"]], [".github/workflows/build.yml"])

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no workflow matched", facts["reason"])
        self.assertIn("no CODEOWNERS file at", facts["reason"])
        self.assertEqual(facts["reports"], [])
        self.assertEqual(facts["unparsed"], [])

    def test_says_it_found_nothing_when_the_only_workflow_could_not_be_read(self):
        facts = self.collect(self.workspace(**at("anchored.yml", ANCHORED)))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no workflow could be read", facts["reason"])
        self.assertEqual(len(facts["unparsed"]), 1)

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**dict(at("build.yml", BUILD), **at("pins.yml", PINS)))

        facts = self.collect(workspace, workflows=".github/workflows/pins.yml")

        self.assertEqual([report["path"] for report in facts["reports"]], [".github/workflows/pins.yml"])

    def test_reads_the_workflows_of_this_repository(self):
        workspace = self.workspace()
        shutil.copytree(OWN_WORKFLOWS, os.path.join(workspace, ".github", "workflows"))

        facts = self.collect(workspace)
        steps = [step for workflow in facts["workflows"] for job in workflow["jobs"] for step in job["steps"]]

        definitions = [name for name in os.listdir(OWN_WORKFLOWS) if name.endswith((".yml", ".yaml"))]

        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["counts"]["workflows"], len(definitions))
        self.assertGreater(facts["counts"]["jobs"], 0)
        self.assertTrue([step for step in steps if step["uses"] and not step["pinned"]])


    def test_reads_every_rule_in_file_order(self):
        facts = self.owned("README.md")

        self.assertEqual(
            [rule["pattern"] for rule in facts["rules"]],
            ["*", "*.md", "/build/logs/", "apps/", "lib/**/vendor", "/service/generated/"],
        )
        self.assertEqual([rule["line"] for rule in facts["rules"]], [3, 5, 7, 9, 11, 14])
        self.assertEqual(facts["unparsed"], [])

    def test_ignores_comments_and_blank_lines(self):
        facts = self.owned("README.md")

        self.assertEqual(len(facts["rules"]), 6)
        self.assertEqual(facts["rules"][1]["owners"], ["@company/docs", "docs@company.example"])

    def test_counts_the_rules_that_name_each_owner(self):
        facts = self.owned("README.md")

        self.assertEqual(facts["owners"], {
            "@company/platform": 1,
            "@company/docs": 1,
            "docs@company.example": 1,
            "@company/observability": 1,
            "@company/apps": 1,
            "@company/vendors": 1,
        })

    def test_a_star_owns_every_path_at_every_depth(self):
        facts = self.owned("Makefile,service/src/main/kotlin/Queue.kt")

        self.assertEqual(facts["matched"]["Makefile"]["owners"], ["@company/platform"])
        self.assertEqual(facts["matched"]["service/src/main/kotlin/Queue.kt"]["owners"], ["@company/platform"])

    def test_the_last_rule_to_match_a_path_is_the_one_github_gives_it(self):
        matched = self.owned("docs/guide.md")["matched"]["docs/guide.md"]

        self.assertEqual(matched["owners"], ["@company/docs", "docs@company.example"])
        self.assertEqual(matched["rule"], "*.md")
        self.assertEqual(matched["line"], 5)

    def test_a_pattern_with_no_slash_matches_at_any_depth(self):
        facts = self.owned("notes.md,deep/nested/notes.md")

        self.assertEqual(facts["matched"]["notes.md"]["rule"], "*.md")
        self.assertEqual(facts["matched"]["deep/nested/notes.md"]["rule"], "*.md")

    def test_a_leading_slash_anchors_the_pattern_to_the_repository_root(self):
        facts = self.owned("build/logs/app.log,service/build/logs/app.log")

        self.assertEqual(facts["matched"]["build/logs/app.log"]["owners"], ["@company/observability"])
        self.assertEqual(facts["matched"]["service/build/logs/app.log"]["owners"], ["@company/platform"])

    def test_a_trailing_slash_owns_the_directory_and_everything_under_it(self):
        facts = self.owned("build/logs/nested/deep/app.log,service/apps/main.js,apps/main.js")

        self.assertEqual(facts["matched"]["build/logs/nested/deep/app.log"]["rule"], "/build/logs/")
        self.assertEqual(facts["matched"]["service/apps/main.js"]["owners"], ["@company/apps"])
        self.assertEqual(facts["matched"]["apps/main.js"]["owners"], ["@company/apps"])

    def test_a_double_star_spans_directories(self):
        facts = self.owned("lib/vendor,lib/queue/native/vendor,lib/vendored")

        self.assertEqual(facts["matched"]["lib/vendor"]["owners"], ["@company/vendors"])
        self.assertEqual(facts["matched"]["lib/queue/native/vendor"]["owners"], ["@company/vendors"])
        self.assertEqual(facts["matched"]["lib/vendored"]["owners"], ["@company/platform"])

    def test_a_rule_with_no_owners_removes_ownership(self):
        matched = self.owned("service/generated/schema.kt")["matched"]["service/generated/schema.kt"]

        self.assertEqual(matched["owners"], [])
        self.assertEqual(matched["rule"], "/service/generated/")
        self.assertEqual(matched["line"], 14)

    def test_a_path_no_rule_matches_has_no_owners_at_all(self):
        matched = self.owned("src/main.py", codeowners=SCOPED)["matched"]["src/main.py"]

        self.assertEqual(matched["owners"], [])
        self.assertIsNone(matched["rule"])
        self.assertIsNone(matched["line"])

    def test_resolves_a_path_written_from_the_repository_root(self):
        facts = self.owned("/docs/guide.md", codeowners=SCOPED)

        self.assertEqual(facts["matched"]["/docs/guide.md"]["owners"], ["@company/docs"])

    def test_a_bracketed_line_is_a_pattern_because_github_has_no_sections(self):
        facts = self.owned("[Documentation]", codeowners=BRACKETED)

        self.assertEqual(facts["unparsed"], [])
        self.assertEqual([rule["pattern"] for rule in facts["rules"]], ["*", "[Documentation]"])
        self.assertEqual(facts["rules"][1]["owners"], [])
        self.assertEqual(facts["matched"]["[Documentation]"]["rule"], "[Documentation]")

    def test_brackets_are_literal_because_github_defines_no_character_range(self):
        facts = self.owned("D", codeowners=BRACKETED)

        self.assertEqual(facts["matched"]["D"]["rule"], "*")

    def test_says_which_lines_are_not_a_rule(self):
        facts = self.owned("src/main.py", codeowners=MALFORMED)

        self.assertEqual(facts["unparsed"], [
            {"line": 1, "reason": "'platform-team' is not a GitHub user, a GitHub team or an email address"},
        ])
        self.assertEqual([rule["pattern"] for rule in facts["rules"]], ["/src/"])
        self.assertEqual(facts["matched"]["src/main.py"]["owners"], ["@company/platform"])

    def test_reads_the_file_the_github_directory_carries(self):
        facts = self.owned("README.md", location=".github/CODEOWNERS")

        self.assertEqual(facts["path"], ".github/CODEOWNERS")

    def test_reads_the_file_the_docs_directory_carries(self):
        facts = self.owned("README.md", location="docs/CODEOWNERS")

        self.assertEqual(facts["path"], "docs/CODEOWNERS")

    def test_prefers_the_github_directory_over_the_other_two_locations(self):
        workspace = self.workspace(**{
            ".github/CODEOWNERS": OWNERS,
            "CODEOWNERS": SCOPED,
            "docs/CODEOWNERS": SCOPED,
        })
        facts = self.collect(workspace, paths="README.md")

        self.assertEqual(facts["codeowners"]["path"], ".github/CODEOWNERS")

    def test_prefers_the_root_file_over_the_docs_one(self):
        workspace = self.workspace(**{
            "CODEOWNERS": OWNERS,
            "docs/CODEOWNERS": SCOPED,
        })
        facts = self.collect(workspace, paths="README.md")

        self.assertEqual(facts["codeowners"]["path"], "CODEOWNERS")

    def test_names_the_codeowners_file_it_read(self):
        facts = self.collect(self.workspace(**{"CODEOWNERS": OWNERS, "README.md": "# Widget\n"}))
        report = facts["reports"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["codeowners"]["path"], "CODEOWNERS")
        self.assertEqual(report["path"], "CODEOWNERS")
        self.assertEqual(report["format"], "codeowners")
        self.assertIsNotNone(report["modified"])

    def test_leaves_codeowners_out_when_the_repository_carries_none(self):
        facts = self.collect(self.workspace(**at("build.yml", BUILD)))

        self.assertNotIn("codeowners", facts)

    def test_leaves_the_workflows_out_when_the_repository_carries_none(self):
        facts = self.collect(self.workspace(**{"CODEOWNERS": OWNERS}))

        self.assertNotIn("workflows", facts)
        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["codeowners"]["path"], "CODEOWNERS")


if __name__ == "__main__":
    unittest.main()
