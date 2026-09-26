#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("build.yml")

BARE = fixture("bare.yml")

HEADERS = fixture("headers.yml")

TIMEOUTS = fixture("timeouts.yml")

LITERAL = "hunter2-must-not-appear"

SECRETS = fixture("secrets.yml") % LITERAL

ANCHORED = fixture("anchored.yml")


OWNERS = fixture("owners.codeowners")

NESTED = fixture("nested.codeowners")

SCOPED = """[Docs] @company/docs
/docs/
"""

MALFORMED = fixture("malformed.codeowners")

class GitLabTest(CollectorTestCase):
    COLLECTOR = "gitlab"

    def owned(self, paths, codeowners=OWNERS, location="CODEOWNERS"):
        workspace = self.workspace(**{location: codeowners, "README.md": "# Widget\n"})

        return self.collect(workspace, paths=paths)["codeowners"]

    def test_reads_a_pipeline(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))
        pipeline = facts["pipelines"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(pipeline["path"], ".gitlab-ci.yml")
        self.assertEqual(pipeline["stages"], ["build", "deploy"])
        self.assertEqual(facts["stages"], ["build", "deploy"])
        self.assertEqual(pipeline["image"], "alpine:3.19")
        self.assertEqual(pipeline["default"], {"image": "gradle:8.10"})
        self.assertEqual(pipeline["variables"], ["GRADLE_OPTS", "REGION"])
        self.assertEqual(pipeline["workflowRules"], 2)
        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["counts"], {"pipelines": 1, "jobs": 3, "scripts": 4})

    def test_names_the_file_it_read(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], ".gitlab-ci.yml")
        self.assertEqual(report["format"], "gitlab-ci")
        self.assertIsNotNone(report["modified"])

    def test_names_what_the_pipeline_includes(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))

        self.assertEqual(facts["pipelines"][0]["includes"], [
            ".gitlab/shared.yml",
            "company/templates",
            "https://example.com/remote.yml",
        ])

    def test_reads_a_job(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))
        build, deploy, downstream = facts["pipelines"][0]["jobs"]

        self.assertEqual(build["id"], "build")
        self.assertEqual(build["stage"], "build")
        self.assertEqual(build["image"], "gradle:8.10-jdk21")
        self.assertEqual(build["tags"], ["docker", "linux"])
        self.assertTrue(build["interruptible"])
        self.assertFalse(build["allowFailure"])
        self.assertEqual(build["extends"], [".template"])
        self.assertEqual(build["variables"], ["STEP"])
        self.assertEqual(build["rules"], 0)
        self.assertIsNone(build["when"])
        self.assertIsNone(build["trigger"])
        self.assertEqual(deploy["when"], "manual")
        self.assertTrue(deploy["allowFailure"])
        self.assertEqual(deploy["needs"], ["build", "lint"])
        self.assertEqual(deploy["environment"], {"name": "production"})
        self.assertEqual(deploy["rules"], 1)
        self.assertEqual(downstream["trigger"], {"project": "company/infra"})

    def test_leaves_out_a_reserved_key_and_a_hidden_one(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))

        self.assertEqual([job["id"] for job in facts["pipelines"][0]["jobs"]], ["build", "deploy", "downstream"])

    def test_reads_every_script_section_in_the_order_they_run(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))
        build = facts["pipelines"][0]["jobs"][0]

        self.assertEqual([script["section"] for script in build["scripts"]],
                         ["before_script", "script", "after_script"])
        self.assertEqual(build["scripts"][1]["run"],
                         './gradlew check\necho "built $CI_COMMIT_SHA on ${CI_COMMIT_BRANCH}"')

    def test_collects_the_variables_a_script_interpolates(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BUILD}))
        script = facts["pipelines"][0]["jobs"][0]["scripts"][1]

        self.assertEqual(script["variables"], ["CI_COMMIT_SHA", "CI_COMMIT_BRANCH"])

    def test_reads_a_timeout_as_gitlab_writes_it_and_in_minutes(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": TIMEOUTS}))
        short, long, seconds, odd, none = facts["pipelines"][0]["jobs"]

        self.assertEqual((short["timeout"], short["timeoutMinutes"]), ("45m", 45))
        self.assertEqual((long["timeout"], long["timeoutMinutes"]), ("1h 30m", 90))
        self.assertEqual((seconds["timeout"], seconds["timeoutMinutes"]), ("3600", 60))
        self.assertEqual((odd["timeout"], odd["timeoutMinutes"]), ("a fortnight", None))
        self.assertEqual((none["timeout"], none["timeoutMinutes"]), (None, None))

    def test_collects_secret_names_and_no_secret_values(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": SECRETS}))
        job = facts["pipelines"][0]["jobs"][0]

        self.assertEqual(job["secretsUsed"], ["DEPLOY_TOKEN"])
        self.assertEqual(job["variables"], ["TOKEN"])
        self.assertNotIn(LITERAL, json.dumps(facts))

    def test_truncates_a_long_script_but_reads_the_whole_of_it_first(self):
        body = "\n".join(["    - echo %d" % number for number in range(400)] + ["    - echo $CI_COMMIT_TITLE"])
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": "build:\n  script:\n%s\n" % body}))
        script = facts["pipelines"][0]["jobs"][0]["scripts"][0]

        self.assertEqual(len(script["run"]), 2000)
        self.assertEqual(script["variables"], ["CI_COMMIT_TITLE"])

    def test_reads_a_job_that_declares_nothing_but_a_script(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BARE}))
        pipeline = facts["pipelines"][0]
        job = pipeline["jobs"][0]

        self.assertEqual(pipeline["stages"], [])
        self.assertIsNone(pipeline["image"])
        self.assertIsNone(pipeline["default"])
        self.assertEqual(pipeline["variables"], [])
        self.assertEqual(pipeline["includes"], [])
        self.assertEqual(pipeline["workflowRules"], 0)
        self.assertIsNone(job["stage"])
        self.assertIsNone(job["image"])
        self.assertEqual(job["tags"], [])
        self.assertEqual(job["needs"], [])
        self.assertIsNone(job["environment"])
        self.assertEqual(job["extends"], [])
        self.assertEqual(job["secretsUsed"], [])

    def test_leaves_out_the_keys_gitlab_reserves_for_the_file_itself(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": HEADERS}))

        self.assertEqual([job["id"] for job in facts["pipelines"][0]["jobs"]], ["build"])

    def test_reads_nothing_that_is_not_a_gitlab_ci_file(self):
        facts = self.collect(self.workspace(**{"pipeline.yml": BUILD}))

        self.assertEqual(facts["source"], "none")
        self.assertEqual(facts["reports"], [])

    def test_records_a_file_outside_the_yaml_subset_rather_than_guessing_at_it(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": ANCHORED}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no GitLab CI file could be read", facts["reason"])
        self.assertEqual(facts["unparsed"], [{"path": ".gitlab-ci.yml", "reason": "anchor at line 1"}])

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no GitLab CI file matched", facts["reason"])
        self.assertIn("no CODEOWNERS file at", facts["reason"])
        self.assertEqual(facts["reports"], [])
        self.assertEqual(facts["unparsed"], [])

    def test_honours_the_globs_it_is_given(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BARE}), pipelines=".gitlab-ci.yaml")

        self.assertEqual(facts["source"], "none")


    def test_reads_every_section_in_file_order_with_the_rules_written_under_it(self):
        sections = self.owned("README.md")["sections"]

        self.assertEqual(
            [section["name"] for section in sections],
            ["codeowners", "Backend", "Documentation", "Security review", "Generated"],
        )
        self.assertEqual([section["line"] for section in sections], [None, 5, 9, 13, 16])
        self.assertEqual(
            [[rule["pattern"] for rule in section["rules"]] for section in sections],
            [["*"], ["/api/", "/service/"], ["*.md", "/docs/"], ["/terraform/"], ["/service/generated/"]],
        )

    def test_a_rule_above_the_first_header_belongs_to_the_implicit_default_section(self):
        leading = self.owned("README.md")["sections"][0]

        self.assertTrue(leading["implicit"])
        self.assertFalse(leading["optional"])
        self.assertEqual(leading["defaultOwners"], [])
        self.assertEqual(leading["rules"], [{
            "pattern": "*",
            "owners": ["@company/platform"],
            "inherited": False,
            "line": 3,
        }])

    def test_reads_the_approvals_a_section_asks_for_and_whether_it_is_optional(self):
        sections = dict((section["name"], section) for section in self.owned("README.md")["sections"])

        self.assertEqual(sections["Backend"]["approvalsRequired"], 2)
        self.assertFalse(sections["Backend"]["optional"])
        self.assertIsNone(sections["Security review"]["approvalsRequired"])
        self.assertTrue(sections["Security review"]["optional"])
        self.assertFalse(sections["Backend"]["implicit"])

    def test_a_rule_naming_no_owner_takes_the_owners_its_section_header_declares(self):
        sections = dict((section["name"], section) for section in self.owned("README.md")["sections"])

        self.assertEqual(sections["Documentation"]["defaultOwners"], ["@company/docs", "docs@company.example"])
        self.assertEqual(sections["Backend"]["rules"][0]["owners"], ["@company/backend"])
        self.assertTrue(sections["Backend"]["rules"][0]["inherited"])
        self.assertEqual(sections["Backend"]["rules"][1]["owners"], ["@company/service-team"])
        self.assertFalse(sections["Backend"]["rules"][1]["inherited"])

    def test_counts_the_rules_each_owner_ends_up_owning(self):
        self.assertEqual(self.owned("README.md")["owners"], {
            "@company/platform": 1,
            "@company/backend": 1,
            "@company/service-team": 1,
            "@company/docs": 2,
            "docs@company.example": 2,
            "@company/security/appsec": 1,
        })

    def test_a_path_is_owned_by_every_section_that_matches_it(self):
        matched = self.owned("docs/guide.md")["matched"]["docs/guide.md"]

        self.assertEqual([entry["section"] for entry in matched["sections"]], ["codeowners", "Documentation"])
        self.assertEqual(matched["owners"], ["@company/platform", "@company/docs", "docs@company.example"])

    def test_the_last_matching_rule_of_each_section_decides_that_sections_owners(self):
        matched = self.owned("docs/guide.md")["matched"]["docs/guide.md"]
        documentation = matched["sections"][1]

        self.assertEqual(documentation["rule"], "/docs/")
        self.assertEqual(documentation["line"], 11)
        self.assertEqual(documentation["owners"], ["@company/docs", "docs@company.example"])
        self.assertFalse(documentation["optional"])
        self.assertIsNone(documentation["approvalsRequired"])

    def test_an_optional_section_owns_a_path_without_its_approval_being_required(self):
        matched = self.owned("terraform/main.tf")["matched"]["terraform/main.tf"]
        security = matched["sections"][1]

        self.assertEqual(security["section"], "Security review")
        self.assertTrue(security["optional"])
        self.assertEqual(security["owners"], ["@company/security/appsec"])

    def test_a_leading_slash_anchors_a_pattern_to_the_project_root(self):
        facts = self.owned("api/routes.kt,service/api/routes.kt")

        self.assertEqual(facts["matched"]["api/routes.kt"]["sections"][1]["rule"], "/api/")
        self.assertEqual(facts["matched"]["service/api/routes.kt"]["sections"][1]["rule"], "/service/")

    def test_a_pattern_with_no_slash_matches_at_any_depth(self):
        facts = self.owned("notes.md,deep/nested/notes.md")

        self.assertEqual(facts["matched"]["notes.md"]["sections"][1]["rule"], "*.md")
        self.assertEqual(facts["matched"]["deep/nested/notes.md"]["sections"][1]["rule"], "*.md")

    def test_a_double_star_spans_directories(self):
        facts = self.owned("lib/vendor,lib/queue/native/vendor,lib/vendored", codeowners=NESTED)

        self.assertEqual(facts["matched"]["lib/vendor"]["owners"], ["@company/vendors"])
        self.assertEqual(facts["matched"]["lib/queue/native/vendor"]["owners"], ["@company/vendors"])
        self.assertEqual(facts["matched"]["lib/vendored"]["sections"], [])

    def test_a_trailing_slash_owns_the_directory_and_everything_under_it(self):
        facts = self.owned("apps/main.js,service/apps/nested/main.js", codeowners=NESTED)

        self.assertEqual(facts["matched"]["apps/main.js"]["owners"], ["@company/apps"])
        self.assertEqual(facts["matched"]["service/apps/nested/main.js"]["owners"], ["@company/apps"])

    def test_a_rule_naming_no_owner_under_a_section_declaring_none_owns_nothing(self):
        matched = self.owned("service/generated/schema.kt")["matched"]["service/generated/schema.kt"]
        generated = matched["sections"][2]

        self.assertEqual(generated["section"], "Generated")
        self.assertEqual(generated["rule"], "/service/generated/")
        self.assertEqual(generated["owners"], [])
        self.assertEqual(matched["owners"], ["@company/platform", "@company/service-team"])

    def test_a_path_no_section_matches_has_no_owners_at_all(self):
        matched = self.owned("src/main.py", codeowners=SCOPED)["matched"]["src/main.py"]

        self.assertEqual(matched["sections"], [])
        self.assertEqual(matched["owners"], [])

    def test_resolves_a_path_written_from_the_project_root(self):
        facts = self.owned("/docs/guide.md", codeowners=SCOPED)

        self.assertEqual(facts["matched"]["/docs/guide.md"]["owners"], ["@company/docs"])

    def test_says_which_lines_are_neither_a_rule_nor_a_section_header(self):
        facts = self.owned("src/main.py", codeowners=MALFORMED)

        self.assertEqual(facts["unparsed"], [
            {"line": 1, "reason": "'[Unclosed' is no closed section header"},
            {"line": 2, "reason": "'platform-team' is no user, group or email address"},
            {
                "line": 3,
                "reason": "'engineering' is no user, group or email address, so the section does not default to it",
            },
        ])
        self.assertEqual([section["name"] for section in facts["sections"]], ["Backend"])
        self.assertEqual(facts["matched"]["src/main.py"]["owners"], ["@company/platform"])

    def test_reads_the_file_the_gitlab_directory_carries(self):
        facts = self.owned("README.md", location=".gitlab/CODEOWNERS")

        self.assertEqual(facts["path"], ".gitlab/CODEOWNERS")

    def test_reads_the_file_the_docs_directory_carries(self):
        facts = self.owned("README.md", location="docs/CODEOWNERS")

        self.assertEqual(facts["path"], "docs/CODEOWNERS")

    def test_names_the_codeowners_file_it_read(self):
        facts = self.collect(self.workspace(**{"CODEOWNERS": OWNERS, "README.md": "# Widget\n"}))
        report = facts["reports"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["codeowners"]["path"], "CODEOWNERS")
        self.assertEqual(report["path"], "CODEOWNERS")
        self.assertEqual(report["format"], "codeowners")
        self.assertIsNotNone(report["modified"])

    def test_leaves_codeowners_out_when_the_repository_carries_none(self):
        facts = self.collect(self.workspace(**{".gitlab-ci.yml": BARE}))

        self.assertNotIn("codeowners", facts)

    def test_leaves_the_pipelines_out_when_the_repository_carries_none(self):
        facts = self.collect(self.workspace(**{"CODEOWNERS": OWNERS}))

        self.assertNotIn("pipelines", facts)
        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["codeowners"]["path"], "CODEOWNERS")

    def test_says_it_found_no_codeowners_file_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "# Widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no CODEOWNERS file at", facts["reason"])
        self.assertEqual(facts["reports"], [])


if __name__ == "__main__":
    unittest.main()
