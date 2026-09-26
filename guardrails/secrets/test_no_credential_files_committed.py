#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))

from guardrail_testing import GuardrailTestCase, unreadable_is_enforced

SECRET = "s3cr3t-value-that-must-never-leave-the-collector"

BUNDLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guardrails.json")

with open(BUNDLE, encoding="utf-8") as handle:
    PATHS = json.load(handle)["guardrails"]["no-credential-files-committed"]["inputs"]["paths"]["default"]

CLEAN = {"README.md": "widget\n", ".env.example": "STRIPE_API_KEY=\n", ".gitignore": ".env\n"}


class NoCredentialFilesCommittedTest(GuardrailTestCase):
    SCRIPT = "no-credential-files-committed.py"
    COLLECT = ["files"]

    def check(self, directory, **inputs):
        inputs.setdefault("paths", PATHS)

        return GuardrailTestCase.check(self, directory, **inputs)

    def assert_flagged(self, *names):
        directory = self.workspace(**dict((name, "value\n") for name in names))
        result = self.check(directory)

        self.assertEqual(result.code, 1, result.payload)
        self.assertEqual(
            sorted(violation["message"] for violation in result.violations),
            sorted("Credential file %s is in the checkout. Take it out of the repository, rotate whatever "
                   "it carried and ignore the path." % name for name in names),
        )

    def test_passes_a_checkout_carrying_no_credential_file(self):
        self.assert_passed(self.check(self.workspace(**CLEAN)))

    def test_fails_a_dotenv_file(self):
        self.assert_flagged(".env")

    def test_fails_an_environment_specific_dotenv_file(self):
        self.assert_flagged(".env.local", ".env.development", ".env.production", ".env.test")

    def test_fails_a_private_key(self):
        self.assert_flagged("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")

    def test_fails_a_keystore(self):
        self.assert_flagged("keystore.jks", "keystore.p12", "release.keystore")

    def test_fails_a_kubeconfig(self):
        self.assert_flagged("kubeconfig", ".kube/config")

    def test_fails_a_cloud_credential_file(self):
        self.assert_flagged(".aws/credentials")

    def test_fails_a_registry_credential_file(self):
        self.assert_flagged(".npmrc", ".netrc")

    def test_reports_every_credential_file_in_the_checkout(self):
        directory = self.workspace(**{".env": "K=v\n", "id_rsa": "key\n", "README.md": "widget\n"})

        self.assertEqual(len(self.check(directory).violations), 2)

    def test_carries_the_path_and_its_size_as_evidence(self):
        directory = self.workspace(**{".env": "STRIPE_API_KEY=abc\n"})

        violation = self.assert_violation(self.check(directory), "Credential file .env is in the checkout")

        self.assertEqual(violation["evidence"], ".env (19 bytes)")

    def test_honours_the_paths_it_is_given(self):
        directory = self.workspace(**{".env": "K=v\n", "service-account.json": "{}\n"})

        self.assert_violation(
            self.check(directory, paths="service-account.json"),
            "Credential file service-account.json is in the checkout",
        )
        self.assert_passed(self.check(directory, paths="deploy/service-account.json"))

    def test_skips_a_pattern_it_cannot_answer(self):
        self.assert_skipped(
            self.check(self.workspace(**CLEAN), paths=".env,*.pem,id_rsa"),
            "*.pem is a pattern, and this guardrail reads exact paths",
        )

    def test_reports_a_credential_file_it_cannot_read(self):
        if not unreadable_is_enforced():
            self.skip("this process reads a file whatever its mode")

        directory = self.workspace(**{".env": "STRIPE_API_KEY=abc\n"})
        os.chmod(os.path.join(directory, ".env"), 0)

        violation = self.assert_violation(self.check(directory), "Credential file .env is in the checkout")

        self.assertEqual(violation["evidence"], ".env (unreadable)")

    def test_never_carries_what_the_file_holds_into_its_output(self):
        directory = self.workspace(**{".env": "STRIPE_API_KEY=%s\n" % SECRET})
        result = self.check(directory)

        self.assertEqual(result.code, 1)
        self.assertNotIn(SECRET, json.dumps(result.payload))


if __name__ == "__main__":
    unittest.main()
