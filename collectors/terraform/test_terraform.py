#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import CollectorTestCase, fixtures

fixture = fixtures(__file__)

NO_BACKEND = fixture("no-backend.tf")

S3_BACKEND = fixture("s3-backend.tf")

PLAIN_BACKEND = fixture("plain-backend.tf")

PROVIDERS = fixture("providers.tf")

MODULES = fixture("modules.tf")

LOCK = fixture("lock.hcl")

SECRET = "s3cr3t-default-nobody-should-collect"

VARIABLES = fixture("variables.tf") % SECRET

TFVARS_SECRET = "hunter2-tfvars-literal"

TFVARS = fixture("live.tfvars") % TFVARS_SECRET

BROKEN = fixture("broken.tf")

AWKWARD = fixture("awkward.tf")

STATE = '{"version": 4, "serial": 12}'

INSTALLED = ".terraform/providers/registry.terraform.io/hashicorp/aws/6.4.0/linux_amd64/terraform-provider-aws"

SELECTIONS = json.dumps({
    "terraform_version": "1.9.5",
    "provider_selections": {
        "registry.terraform.io/hashicorp/aws": "6.4.0",
        "registry.terraform.io/hashicorp/random": "3.6.3",
    },
})


class TerraformTest(CollectorTestCase):
    COLLECTOR = "terraform"

    def test_calls_a_root_with_no_backend_block_local(self):
        facts = self.collect(self.workspace(**{"main.tf": NO_BACKEND}))
        root = facts["roots"][0]

        self.assertEqual(facts["source"], "report")
        self.assertEqual(root["path"], ".")
        self.assertEqual(root["backend"]["type"], "local")
        self.assertEqual(root["backend"]["attributes"], {})
        self.assertIsNone(root["backend"]["encrypted"])
        self.assertIsNone(root["backend"]["locking"])
        self.assertEqual(root["unparsed"], 0)
        self.assertEqual(root["varFiles"], [])
        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["stateFiles"], [])

    def test_reads_an_s3_backend_with_encryption_and_locking(self):
        facts = self.collect(self.workspace(**{"main.tf": S3_BACKEND}))
        backend = facts["roots"][0]["backend"]

        self.assertEqual(backend["type"], "s3")
        self.assertEqual(backend["encrypted"], True)
        self.assertEqual(backend["locking"], True)
        self.assertEqual(backend["attributes"]["bucket"], "widget-terraform-state")
        self.assertEqual(backend["attributes"]["key"], "live/widget.tfstate")
        self.assertIn("secret_key", backend["attributes"])
        self.assertIsNone(backend["attributes"]["secret_key"])
        self.assertNotIn("AKIAIOSFODNN7SECRETLITERAL", json.dumps(facts))

    def test_reads_a_local_backend_that_is_declared(self):
        facts = self.collect(self.workspace(**{"main.tf": PLAIN_BACKEND}))
        backend = facts["roots"][0]["backend"]

        self.assertEqual(backend["type"], "local")
        self.assertEqual(backend["attributes"], {"path": "terraform.tfstate"})
        self.assertIsNone(backend["locking"])

    def test_tells_a_pinned_provider_from_a_constrained_one(self):
        facts = self.collect(self.workspace(**{"main.tf": PROVIDERS}))
        providers = dict((it["name"], it) for it in facts["roots"][0]["providers"])

        self.assertEqual(providers["aws"]["source"], "hashicorp/aws")
        self.assertEqual(providers["aws"]["version"], "6.4.0")
        self.assertTrue(providers["aws"]["pinned"])
        self.assertEqual(providers["random"]["version"], "~> 3.6")
        self.assertFalse(providers["random"]["pinned"])
        self.assertTrue(providers["tls"]["pinned"])
        self.assertIsNone(providers["vault"]["source"])
        self.assertIsNone(providers["vault"]["version"])
        self.assertFalse(providers["vault"]["pinned"])

    def test_reads_a_module_from_the_registry_from_git_and_from_a_path(self):
        facts = self.collect(self.workspace(**{"main.tf": MODULES}))
        modules = dict((it["name"], it) for it in facts["roots"][0]["modules"])

        self.assertEqual(modules["events"]["source"], "terraform-aws-modules/sqs/aws")
        self.assertEqual(modules["events"]["version"], "4.2.1")
        self.assertEqual(
            [modules["events"][it] for it in ("local", "registry", "git")],
            [False, True, False],
        )
        self.assertEqual(
            [modules["policy"][it] for it in ("local", "registry", "git")],
            [False, False, True],
        )
        self.assertIsNone(modules["policy"]["version"])
        self.assertEqual(
            [modules["site"][it] for it in ("local", "registry", "git")],
            [True, False, False],
        )

    def test_reads_the_lock_file_for_versions_and_hash_counts(self):
        facts = self.collect(self.workspace(**{"main.tf": PROVIDERS, ".terraform.lock.hcl": LOCK}))
        lockfile = facts["roots"][0]["lockfile"]
        locked = dict((it["name"], it) for it in lockfile["providers"])

        self.assertTrue(lockfile["present"])
        self.assertEqual(lockfile["path"], ".terraform.lock.hcl")
        self.assertEqual(locked["aws"]["source"], "registry.terraform.io/hashicorp/aws")
        self.assertEqual(locked["aws"]["version"], "6.4.0")
        self.assertEqual(locked["aws"]["hashes"], 3)
        self.assertEqual(locked["random"]["hashes"], 1)
        self.assertNotIn("h1:Ov0RQL0hAAoW5tsvKGZTP0AeYnJ5jFkzz5RTaBWivUE=", json.dumps(facts))

    def test_says_when_a_root_commits_no_lock_file(self):
        facts = self.collect(self.workspace(**{"main.tf": NO_BACKEND}))

        self.assertEqual(
            facts["roots"][0]["lockfile"],
            {"present": False, "path": None, "providers": []},
        )

    def test_finds_a_state_file_left_in_the_tree(self):
        facts = self.collect(self.workspace(**{
            "main.tf": NO_BACKEND,
            "terraform.tfstate": STATE,
            ".terraform/terraform.tfstate": '{"version": 4}',
        }))

        self.assertEqual([it["path"] for it in facts["stateFiles"]], ["terraform.tfstate"])
        self.assertEqual(facts["stateFiles"][0]["bytes"], len(STATE))

    def test_collects_variable_names_without_their_defaults(self):
        facts = self.collect(self.workspace(**{"main.tf": VARIABLES}))
        variables = dict((it["name"], it) for it in facts["roots"][0]["variables"])

        self.assertEqual(sorted(variables), ["api_token", "domain_name", "region"])
        self.assertTrue(variables["api_token"]["sensitive"])
        self.assertTrue(variables["api_token"]["hasDefault"])
        self.assertFalse(variables["region"]["sensitive"])
        self.assertFalse(variables["domain_name"]["hasDefault"])
        self.assertNotIn(SECRET, json.dumps(facts))

    def test_reads_the_names_a_tfvars_file_sets_and_none_of_its_values(self):
        facts = self.collect(self.workspace(**{"main.tf": VARIABLES, "live.tfvars": TFVARS}))
        var_files = facts["roots"][0]["varFiles"]

        self.assertEqual([it["path"] for it in var_files], ["live.tfvars"])
        self.assertEqual(var_files[0]["variables"], ["api_token", "domain_name", "region"])
        self.assertNotIn(TFVARS_SECRET, json.dumps(facts))

    def test_counts_resources_by_type(self):
        configuration = NO_BACKEND + fixture("logs-bucket.tf")
        facts = self.collect(self.workspace(**{"main.tf": configuration}))
        root = facts["roots"][0]

        self.assertEqual(root["resources"], {"aws_s3_bucket": 2})
        self.assertEqual(root["resourceTypes"], ["aws_s3_bucket"])

    def test_reports_a_file_it_cannot_read_rather_than_guessing(self):
        facts = self.collect(self.workspace(**{
            "good/main.tf": NO_BACKEND,
            "broken/main.tf": BROKEN,
        }))
        roots = dict((it["path"], it) for it in facts["roots"])

        self.assertEqual([it["path"] for it in facts["unparsed"]], ["broken/main.tf"])
        self.assertIn("unterminated", facts["unparsed"][0]["reason"])
        self.assertEqual(roots["broken"]["unparsed"], 1)
        self.assertEqual(roots["good"]["unparsed"], 0)
        self.assertEqual([it["path"] for it in facts["reports"]], ["good/main.tf"])

    def test_reads_the_expressions_a_real_configuration_carries(self):
        facts = self.collect(self.workspace(**{"main.tf": AWKWARD}))

        self.assertEqual(facts["unparsed"], [])
        self.assertEqual(facts["roots"][0]["resources"], {"aws_iam_policy": 1})

    def test_describes_every_root_it_finds(self):
        facts = self.collect(self.workspace(**{
            "live/app/main.tf": S3_BACKEND,
            "live/web/main.tf": S3_BACKEND,
            "modules/site/main.tf": NO_BACKEND,
        }))

        self.assertEqual(
            [it["path"] for it in facts["roots"]],
            ["live/app", "live/web", "modules/site"],
        )
        self.assertEqual(
            [it["backend"]["type"] for it in facts["roots"]],
            ["s3", "s3", "local"],
        )

    def test_narrows_discovery_to_the_configured_directory(self):
        workspace = self.workspace(**{"infra/main.tf": S3_BACKEND, "other/main.tf": NO_BACKEND})

        facts = self.collected(workspace, [self.COLLECTOR], {"directory": "infra"})["terraform"]

        self.assertEqual(facts["directory"], "infra")
        self.assertEqual([it["path"] for it in facts["roots"]], ["infra"])

    def test_names_every_file_it_read(self):
        facts = self.collect(self.workspace(**{
            "main.tf": PROVIDERS,
            "live.tfvars": TFVARS,
            ".terraform.lock.hcl": LOCK,
        }))
        read = dict((it["path"], it) for it in facts["reports"])

        self.assertEqual(read["main.tf"]["format"], "tf")
        self.assertEqual(read["live.tfvars"]["format"], "tfvars")
        self.assertEqual(read[".terraform.lock.hcl"]["format"], "lock")
        self.assertIsNotNone(read["main.tf"]["modified"])

    def test_says_it_found_nothing_when_there_is_no_terraform(self):
        facts = self.collect(self.workspace(**{"README.md": "widget\n"}))

        self.assertEqual(facts["source"], "none")
        self.assertIn("no Terraform configuration", facts["reason"])
        self.assertEqual(facts["reports"], [])
        self.assertNotIn("roots", facts)

    def test_records_the_provider_versions_an_initialised_root_resolved(self):
        self.shim(
            "terraform",
            version="Terraform v1.9.5\non darwin_arm64",
            responses=[["providers", SELECTIONS, "", 0]],
        )
        facts = self.collect(self.workspace(**{
            "main.tf": PROVIDERS,
            ".terraform/terraform.tfstate": '{"version": 4}',
            INSTALLED: "terraform-provider-aws\n",
        }))
        resolved = dict((it["name"], it) for it in facts["resolved"])

        self.assertEqual(facts["source"], "tool")
        self.assertEqual(facts["tool"]["name"], "terraform")
        self.assertEqual(facts["tool"]["version"], "1.9.5")
        self.assertEqual(facts["tool"]["args"], ["providers", "-json"])
        self.assertEqual(facts["tool"]["exitCode"], 0)
        self.assertIsNotNone(facts["tool"]["path"])
        self.assertGreaterEqual(facts["tool"]["durationMs"], 0)
        self.assertEqual(resolved["aws"]["version"], "6.4.0")
        self.assertEqual(resolved["aws"]["source"], "registry.terraform.io/hashicorp/aws")
        self.assertEqual(resolved["aws"]["root"], ".")
        self.assertEqual(resolved["random"]["version"], "3.6.3")

    def test_leaves_terraform_alone_when_the_root_is_not_initialised(self):
        self.shim(
            "terraform",
            version="Terraform v1.9.5\non darwin_arm64",
            responses=[["providers", SELECTIONS, "", 0]],
        )
        facts = self.collect(self.workspace(**{
            "main.tf": PROVIDERS,
            ".terraform/terraform.tfstate": '{"version": 4}',
        }))

        self.assertEqual(facts["source"], "report")
        self.assertNotIn("tool", facts)
        self.assertNotIn("resolved", facts)


if __name__ == "__main__":
    unittest.main()
