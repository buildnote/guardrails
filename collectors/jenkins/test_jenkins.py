#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

SHA = "1e204e9a9253d643386038d443f96446fa156a97"

LITERAL = "hunter2-must-not-appear"

BUILD = fixture("build.Jenkinsfile")

BARE = fixture("bare.Jenkinsfile")

EXPRESSED = fixture("expressed.Jenkinsfile")

COMPUTED = fixture("computed.Jenkinsfile")

PARALLEL = fixture("parallel.Jenkinsfile")

TIMEOUTS = fixture("timeouts.Jenkinsfile")

BRACES = fixture("braces.Jenkinsfile")

LIBRARIES = fixture("libraries.Jenkinsfile") % SHA

SCRIPTED = fixture("scripted.Jenkinsfile")

UNCLOSED = fixture("unclosed.Jenkinsfile")

SECRETIVE = fixture("secretive.Jenkinsfile") % (LITERAL, LITERAL)


class JenkinsTest(CollectorTestCase):
    COLLECTOR = "jenkins"

    def test_reads_a_declarative_pipeline(self):
        facts = self.collect(self.workspace(Jenkinsfile=BUILD))
        pipeline = facts["pipelines"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(facts["scanned"], ["Jenkinsfile"])
        self.assertEqual(pipeline["path"], "Jenkinsfile")
        self.assertEqual(pipeline["style"], "declarative")
        self.assertEqual(pipeline["agent"], "docker { image 'maven:3.9.6' }")
        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["counts"], {"pipelines": 1, "stages": 2, "steps": 4})

    def test_names_the_jenkinsfile_it_read(self):
        facts = self.collect(self.workspace(Jenkinsfile=BUILD))
        report = facts["reports"][0]

        self.assertEqual(report["path"], "Jenkinsfile")
        self.assertEqual(report["format"], "jenkins")
        self.assertIsNotNone(report["modified"])

    def test_reads_the_pipeline_options_timeout(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BUILD))["pipelines"][0]

        self.assertEqual(pipeline["timeout"], "timeout(time: 30, unit: 'MINUTES')")
        self.assertEqual(pipeline["timeoutMinutes"], 30)

    def test_reads_the_environment_names_the_triggers_and_the_tools(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BUILD))["pipelines"][0]

        self.assertEqual(pipeline["environment"], ["GRADLE_OPTS", "SONAR_TOKEN"])
        self.assertEqual(pipeline["triggers"], ["cron", "pollSCM"])
        self.assertEqual(pipeline["tools"], ["jdk", "maven"])

    def test_reads_a_stage(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BUILD))["pipelines"][0]
        build, publish = pipeline["stages"]

        self.assertEqual(build["name"], "Build")
        self.assertIsNone(build["parent"])
        self.assertIsNone(build["agent"])
        self.assertIsNone(build["timeout"])
        self.assertIsNone(build["timeoutMinutes"])
        self.assertFalse(build["when"])
        self.assertEqual(publish["agent"], "label 'linux'")
        self.assertEqual(publish["timeout"], "timeout(time: 10, unit: 'MINUTES')")
        self.assertEqual(publish["timeoutMinutes"], 10)
        self.assertTrue(publish["when"])

    def test_reads_the_steps_of_a_stage_with_the_shell_body_where_there_is_one(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BUILD))["pipelines"][0]
        build, publish = pipeline["stages"]

        self.assertEqual(build["steps"], [
            {"name": "checkout", "body": None},
            {"name": "sh", "body": "./gradlew build"},
        ])
        self.assertEqual(publish["steps"], [
            {"name": "withCredentials", "body": None},
            {"name": "sh", "body": "./gradlew publish"},
        ])

    def test_tells_a_branch_of_an_unnamed_stage_from_a_top_level_one(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=EXPRESSED))["pipelines"][0]

        self.assertEqual(
            [(stage["name"], stage["parent"]) for stage in pipeline["stages"]],
            [(None, None), ("Unit", 0)],
        )
        self.assertEqual(pipeline["stages"][0]["timeoutMinutes"], 20)

    def test_reads_a_timeout_whose_argument_is_a_call(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=COMPUTED))["pipelines"][0]

        self.assertEqual(pipeline["stages"][0]["timeout"], "timeout(time: limit(), unit: 'MINUTES')")
        self.assertIsNone(pipeline["stages"][0]["timeoutMinutes"])

    def test_collects_credential_ids_and_no_credential_values(self):
        facts = self.collect(self.workspace(Jenkinsfile=SECRETIVE))

        self.assertEqual(facts["pipelines"][0]["credentials"], ["deploy-token"])
        self.assertNotIn(LITERAL, json.dumps(facts))

    def test_collects_a_credential_id_from_an_environment_binding(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BUILD))["pipelines"][0]

        self.assertEqual(pipeline["credentials"], ["sonar-token", "registry"])

    def test_flattens_a_parallel_branch_into_a_stage_naming_where_its_parent_sits(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=PARALLEL))["pipelines"][0]

        self.assertEqual(
            [(stage["name"], stage["parent"]) for stage in pipeline["stages"]],
            [("Verify", None), ("Unit", 0), ("Integration", 0), ("Provision", 2)],
        )
        self.assertEqual(pipeline["stages"][0]["timeoutMinutes"], 20)
        self.assertIsNone(pipeline["stages"][1]["timeoutMinutes"])

    def test_normalises_a_timeout_to_whole_minutes(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=TIMEOUTS))["pipelines"][0]
        hours, seconds, default, runtime = pipeline["stages"]

        self.assertEqual(hours["timeoutMinutes"], 120)
        self.assertEqual(seconds["timeoutMinutes"], 2)
        self.assertEqual(default["timeoutMinutes"], 45)
        self.assertEqual(runtime["timeout"], "timeout(time: params.LIMIT, unit: 'MINUTES')")
        self.assertIsNone(runtime["timeoutMinutes"])

    def test_records_a_pipeline_that_declares_no_timeout(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BARE))["pipelines"][0]

        self.assertEqual(pipeline["agent"], "any")
        self.assertIsNone(pipeline["timeout"])
        self.assertIsNone(pipeline["timeoutMinutes"])
        self.assertEqual(pipeline["libraries"], [])
        self.assertEqual(pipeline["credentials"], [])

    def test_reads_past_a_brace_inside_a_shell_body_or_a_comment(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BRACES))["pipelines"][0]
        steps = pipeline["stages"][0]["steps"]

        self.assertEqual([stage["name"] for stage in pipeline["stages"]], ["Build"])
        self.assertEqual([step["name"] for step in steps], ["sh", "sh", "echo"])
        self.assertEqual(steps[0]["body"], "echo } not a close brace")
        self.assertIn("for file in *; do", steps[1]["body"])

    def test_splits_a_shared_library_reference_into_a_name_and_a_ref(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=LIBRARIES))["pipelines"][0]

        self.assertEqual(pipeline["libraries"], [
            {"name": "company-shared", "ref": SHA, "pinned": True, "source": "annotation"},
            {"name": "company-legacy", "ref": None, "pinned": False, "source": "annotation"},
            {"name": "company-branchy", "ref": "${env.BRANCH_NAME}", "pinned": False, "source": "annotation"},
            {"name": "company-deploy", "ref": "main", "pinned": False, "source": "step"},
        ])

    def test_pins_a_library_on_a_version_shaped_ref(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=BUILD))["pipelines"][0]

        self.assertEqual(pipeline["libraries"], [
            {"name": "company-pipeline", "ref": "1.4.2", "pinned": True, "source": "annotation"},
        ])

    def test_tells_a_scripted_pipeline_from_a_declarative_one(self):
        pipeline = self.collect(self.workspace(Jenkinsfile=SCRIPTED))["pipelines"][0]

        self.assertEqual(pipeline["style"], "scripted")
        self.assertEqual(pipeline["stages"], [])
        self.assertIsNone(pipeline["agent"])
        self.assertEqual(pipeline["environment"], [])
        self.assertEqual(pipeline["triggers"], [])
        self.assertEqual(pipeline["tools"], [])
        self.assertEqual(pipeline["credentials"], ["npm-token"])
        self.assertEqual(pipeline["libraries"][0]["name"], "company-shared")

    def test_records_a_pipeline_block_it_could_not_close_rather_than_guessing_at_it(self):
        workspace = self.workspace(Jenkinsfile=BUILD, **{"broken.Jenkinsfile": UNCLOSED})

        facts = self.collect(workspace)

        self.assertEqual(facts["unparsed"], [{
            "path": "broken.Jenkinsfile",
            "reason": "the pipeline block on line 1 is never closed",
        }])
        self.assertEqual([pipeline["path"] for pipeline in facts["pipelines"]], ["Jenkinsfile"])

    def test_reads_every_name_the_default_globs_cover(self):
        workspace = self.workspace(**{
            "Jenkinsfile": BARE,
            "Jenkinsfile.release": BARE,
            "nightly.Jenkinsfile": BARE,
            "ci/Jenkinsfile": BARE,
            "notes.groovy": BARE,
        })

        facts = self.collect(workspace)

        self.assertEqual(
            [report["path"] for report in facts["reports"]],
            ["Jenkinsfile", "Jenkinsfile.release", "ci/Jenkinsfile", "nightly.Jenkinsfile"],
        )

    def test_honours_the_globs_it_is_given(self):
        workspace = self.workspace(**{"Jenkinsfile": BARE, "Jenkinsfile.release": BUILD})

        facts = self.collect(workspace, jenkinsfiles="Jenkinsfile.release")

        self.assertEqual([report["path"] for report in facts["reports"]], ["Jenkinsfile.release"])

    def test_says_it_found_nothing_rather_than_collecting_nothing(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no Jenkinsfile matched", facts["reason"])
        self.assertEqual(facts["reports"], [])
        self.assertEqual(facts["unparsed"], [])

    def test_says_it_found_nothing_when_the_only_jenkinsfile_could_not_be_read(self):
        facts = self.collect(self.workspace(Jenkinsfile=UNCLOSED))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no Jenkinsfile could be read", facts["reason"])
        self.assertEqual(len(facts["unparsed"]), 1)

    def test_reads_the_example_it_publishes(self):
        published = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example", "Jenkinsfile")

        with open(published, encoding="utf-8") as handle:
            facts = self.collect(self.workspace(Jenkinsfile=handle.read()))

        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["counts"]["stages"], 5)
        self.assertTrue(facts["pipelines"][0]["libraries"])


if __name__ == "__main__":
    unittest.main()
