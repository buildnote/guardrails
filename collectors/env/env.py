#!/usr/bin/env python3
import os

from guardrail import Collector

PROVIDERS = [
    ("github", "GITHUB_ACTIONS"),
    ("gitlab", "GITLAB_CI"),
    ("circle", "CIRCLECI"),
    ("buildkite", "BUILDKITE"),
    ("teamcity", "TEAMCITY_VERSION"),
    ("bitbucket", "BITBUCKET_BUILD_NUMBER"),
    ("drone", "DRONE"),
    ("travis", "TRAVIS"),
    ("azure", "TF_BUILD"),
    ("jenkins", "JENKINS_URL"),
]

TRIGGERS = ["GITHUB_EVENT_NAME", "CI_PIPELINE_SOURCE", "BUILDKITE_SOURCE", "BUILD_REASON"]

RUNNER_OS = ["RUNNER_OS", "AGENT_OS", "CI_RUNNER_EXECUTABLE_ARCH"]

RUNNER_ARCH = ["RUNNER_ARCH", "CI_RUNNER_EXECUTABLE_ARCH"]

RUNNER_NAME = ["RUNNER_NAME", "AGENT_NAME", "CI_RUNNER_DESCRIPTION", "BUILDKITE_AGENT_NAME", "NODE_NAME"]

PULL_REQUEST = [
    ("GITHUB_EVENT_NAME", ("pull_request", "pull_request_target")),
    ("CI_PIPELINE_SOURCE", ("merge_request_event",)),
    ("BUILD_REASON", ("PullRequest",)),
]

PULL_REQUEST_PRESENT = ["CHANGE_ID", "BITBUCKET_PR_ID", "BUILDKITE_PULL_REQUEST_BASE_BRANCH"]

OIDC = ["ACTIONS_ID_TOKEN_REQUEST_URL", "CI_JOB_JWT_V2", "AWS_WEB_IDENTITY_TOKEN_FILE", "SYSTEM_OIDCREQUESTURI"]

HOSTED = {"github-hosted": True, "self-hosted": False}

INTERESTING = ("CI", "GITHUB_", "GITLAB_", "CI_", "RUNNER_", "AGENT_", "BUILD", "BUILDKITE_", "JENKINS_", "TEAMCITY_")

SECRETISH = ("TOKEN", "SECRET", "PASSWORD", "KEY", "CREDENTIAL", "JWT")


def read(path, collector):
    text = collector.read(path)

    if text is None:
        collector.invalid("%s could not be read" % path)

    entries = {}

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        name, value = stripped.split("=", 1)
        entries[name.strip()] = value.strip()

    return entries


def first(environment, names):
    for name in names:
        value = environment.get(name)

        if value:
            return value

    return None


def truthy(value):
    return str(value).strip().lower() in ("true", "1", "yes")


def provider_of(environment):
    for name, variable in PROVIDERS:
        if environment.get(variable):
            return name

    return "local"


def pull_request_in(environment):
    for name, values in PULL_REQUEST:
        if environment.get(name) in values:
            return True

    return any(environment.get(name) for name in PULL_REQUEST_PRESENT)


def fork_in(environment, provider):
    if provider == "github":
        repository = environment.get("GITHUB_REPOSITORY")
        head = environment.get("GITHUB_HEAD_REPOSITORY")

        return None if not repository or not head else repository != head

    if provider == "gitlab":
        project = environment.get("CI_PROJECT_PATH")
        source = environment.get("CI_MERGE_REQUEST_SOURCE_PROJECT_PATH")

        return None if not project or not source else project != source

    return None


with Collector() as collector:
    configured = collector.input("envFile", "")
    environment = read(configured, collector) if configured else dict(os.environ)

    provider = provider_of(environment)

    collector.facts["provider"] = provider
    collector.facts["ci"] = truthy(environment.get("CI", "")) or provider != "local"
    collector.facts["hosted"] = HOSTED.get(environment.get("RUNNER_ENVIRONMENT", ""))
    collector.facts["trigger"] = first(environment, TRIGGERS)
    collector.facts["pullRequest"] = pull_request_in(environment)
    collector.facts["fork"] = fork_in(environment, provider)
    collector.facts["runner"] = {
        "os": first(environment, RUNNER_OS),
        "arch": first(environment, RUNNER_ARCH),
        "name": first(environment, RUNNER_NAME),
    }
    collector.facts["oidc"] = any(environment.get(name) for name in OIDC)
    collector.facts["variables"] = sorted(
        name for name in environment
        if name.startswith(INTERESTING) and not any(part in name.upper() for part in SECRETISH)
    )
