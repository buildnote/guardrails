#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

BUILD = fixture("build.yml")

MAPPED = fixture("mapped.yml")

STEPS_ONLY = """steps:
  - script: echo hello
"""

EXPRESSIONS = fixture("expressions.yml")

LITERAL = "hunter2-must-not-appear"

SECRETS = fixture("secrets.yml") % LITERAL

TEMPLATED = """jobs:
  - template: jobs/build.yml
"""

ANCHORED = fixture("anchored.yml")


class AzureTest(CollectorTestCase):
    COLLECTOR = "azure"

    def test_reads_a_pipeline(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": BUILD}))
        pipeline = facts["pipelines"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(pipeline["path"], "azure-pipelines.yml")
        self.assertEqual(pipeline["name"], "azure-build")
        self.assertEqual(pipeline["triggers"], ["trigger", "pr", "schedules"])
        self.assertEqual(pipeline["variables"], ["gradleOptions", "deploy-credentials"])
        self.assertEqual(pipeline["stages"], ["build", "deploy"])
        self.assertEqual(facts["stages"], ["build", "deploy"])
        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["counts"], {"pipelines": 1, "jobs": 2, "steps": 4})

    def test_names_the_definition_it_read(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": BUILD}))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "azure-pipelines.yml")
        self.assertEqual(report["format"], "azure")
        self.assertIsNotNone(report["modified"])

    def test_reads_a_job(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": BUILD}))
        compile, release = facts["pipelines"][0]["jobs"]

        self.assertEqual(compile["id"], "compile")
        self.assertEqual(compile["displayName"], "Compile")
        self.assertEqual(compile["stage"], "build")
        self.assertEqual(compile["pool"], {"vmImage": "ubuntu-latest"})
        self.assertEqual(compile["hostedImage"], "ubuntu-latest")
        self.assertFalse(compile["selfHosted"])
        self.assertEqual(compile["timeoutInMinutes"], 30)
        self.assertIsNone(compile["environment"])
        self.assertEqual(compile["dependsOn"], [])
        self.assertIsNone(compile["condition"])
        self.assertIsNone(compile["template"])
        self.assertEqual(release["id"], "release")
        self.assertEqual(release["stage"], "deploy")
        self.assertEqual(release["environment"], "production")
        self.assertEqual(release["dependsOn"], ["compile"])
        self.assertEqual(release["condition"], "succeeded()")
        self.assertIsNone(release["timeoutInMinutes"])

    def test_reads_a_step(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": BUILD}))
        task, script, template = facts["pipelines"][0]["jobs"][0]["steps"]

        self.assertEqual(task["displayName"], "Set up the JDK")
        self.assertEqual(task["task"], "JavaToolInstaller@0")
        self.assertEqual(task["taskName"], "JavaToolInstaller")
        self.assertEqual(task["taskVersion"], "0")
        self.assertEqual(task["inputKeys"], ["versionSpec", "jdkArchitectureOption"])
        self.assertIsNone(task["script"])
        self.assertIsNone(task["shell"])
        self.assertEqual(script["script"], "./gradlew check")
        self.assertEqual(script["shell"], "bash")
        self.assertIsNone(script["task"])
        self.assertEqual(template["template"], "steps/report.yml")

    def test_reads_a_pool_that_names_no_hosted_image(self):
        pipeline = self.collect(self.workspace(**{"azure-pipelines.yml": BUILD}))["pipelines"][0]
        named = self.collect(self.workspace(**{"azure-pipelines.yml": MAPPED}))["pipelines"][0]

        self.assertEqual(pipeline["jobs"][1]["pool"], "on-prem-fleet")
        self.assertIsNone(pipeline["jobs"][1]["hostedImage"])
        self.assertIsNone(pipeline["jobs"][1]["selfHosted"])
        self.assertEqual(named["jobs"][0]["pool"], {"name": "on-prem"})
        self.assertIsNone(named["jobs"][0]["selfHosted"])

    def test_reads_variables_written_as_a_mapping(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": MAPPED}))

        self.assertEqual(facts["pipelines"][0]["variables"], ["region", "fleet"])
        self.assertEqual(facts["pipelines"][0]["stages"], [])

    def test_reads_a_pipeline_written_as_bare_steps_as_the_one_job_it_is(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": STEPS_ONLY}))
        job = facts["pipelines"][0]["jobs"][0]

        self.assertIsNone(job["id"])
        self.assertIsNone(job["displayName"])
        self.assertIsNone(job["stage"])
        self.assertIsNone(job["pool"])
        self.assertEqual(job["steps"][0]["script"], "echo hello")
        self.assertEqual(facts["pipelines"][0]["triggers"], [])
        self.assertEqual(facts["counts"], {"pipelines": 1, "jobs": 1, "steps": 1})

    def test_tells_the_three_expression_syntaxes_apart(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": EXPRESSIONS}))
        step = facts["pipelines"][0]["jobs"][0]["steps"][0]

        self.assertEqual(step["macros"], ["System.PullRequest.SourceBranch"])
        self.assertEqual(step["templateExpressions"], ["parameters.name"])
        self.assertEqual(step["runtimeExpressions"], ["variables.counter"])

    def test_collects_input_names_and_no_input_values(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": SECRETS}))
        step = facts["pipelines"][0]["jobs"][0]["steps"][0]

        self.assertEqual(step["inputKeys"], ["containerRegistry", "password"])
        self.assertNotIn(LITERAL, json.dumps(facts))

    def test_reads_a_job_that_comes_from_a_template(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": TEMPLATED}))
        job = facts["pipelines"][0]["jobs"][0]

        self.assertEqual(job["template"], "jobs/build.yml")
        self.assertEqual(job["steps"], [])

    def test_truncates_a_long_script_but_reads_the_whole_of_it_first(self):
        body = "\n".join(["          echo %d" % number for number in range(400)]
                         + ["          echo $(Build.SourceVersionMessage)"])
        facts = self.collect(self.workspace(**{
            "azure-pipelines.yml": "jobs:\n  - job: long\n    steps:\n      - bash: |\n%s\n" % body
        }))
        step = facts["pipelines"][0]["jobs"][0]["steps"][0]

        self.assertEqual(len(step["script"]), 2000)
        self.assertEqual(step["macros"], ["Build.SourceVersionMessage"])

    def test_records_a_definition_outside_the_yaml_subset_rather_than_guessing_at_it(self):
        facts = self.collect(self.workspace(**{"azure-pipelines.yml": ANCHORED}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no Azure Pipelines definition could be read", facts["reason"])
        self.assertEqual(facts["unparsed"], [{"path": "azure-pipelines.yml", "reason": "anchor at line 1"}])

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no Azure Pipelines definition matched", facts["reason"])
        self.assertEqual(facts["reports"], [])
        self.assertEqual(facts["unparsed"], [])

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"azure-pipelines.yml": STEPS_ONLY, "ci/build.yml": MAPPED})

        facts = self.collect(workspace, pipelines="ci/build.yml")

        self.assertEqual([report["path"] for report in facts["reports"]], ["ci/build.yml"])


if __name__ == "__main__":
    unittest.main()
