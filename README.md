# Buildnote Guardrails

Guardrails are reusable CI policies for Buildnote. Each one is a JSON definition plus a small script that checks a
single rule, such as commit messages following Conventional Commits, Dockerfiles pinning base images by digest or
GitHub Actions workflows declaring token permissions. A failing guardrail can report, comment on a pull request or
fail the build.

The full catalog, with a page per guardrail and per collector, is at
[docs.buildnote.io/reference/guardrails](https://docs.buildnote.io/reference/guardrails/).

## Using a guardrail

List it under `guardrails.checks` in `buildnote.json`:

```json
{
  "guardrails": {
    "checks": [
      { "use": "git/conventional-commits@v1" },
      { "use": "docker/base-pinned@v1", "with": { "registries": "docker.io,ghcr.io" } }
    ]
  }
}
```

A `use` reference is `<category>/<name>@<version>`. Every guardrail in this repository is available without further
configuration. To add guardrails of your own, list more libraries under `guardrails.sources`. They are searched in
order, after the built-in ones:

```json
{
  "guardrails": {
    "sources": ["github://company/our-guardrails", "./guardrails"],
    "checks": [{ "use": "team/no-todo-in-main@v1" }]
  }
}
```

A `github://<owner>/<repository>` source is read over `raw.githubusercontent.com`, and the version in the reference
is the git tag it is read at. A local path is a single version, so the reference's version must match the
definition's own `version`. A `use` string can also carry a `github://<owner>/<repository>/` prefix, pinning that one
reference to that one repository.

A reference no source declares is a configuration error, so a mistyped id never passes quietly. A source that cannot
be reached is missing evidence, and the guardrail is recorded as skipped.

Policies, reporting without gating and every other option are described in
[Configuring guardrails](https://docs.buildnote.io/reference/guardrails/configuration/).

## Versions

A version is a git tag of this repository, and a tag is never moved. Moving one would change a script's SHA-256 and
skip the guardrail for anyone pinning `sha256`. A breaking change, whether to a guardrail or to the layout of the
repository, ships as a new tag, and old tags stay in place.

## Layout

```
guardrails/<category>/guardrails.json
guardrails/<category>/icon.svg
guardrails/<category>/<name>.py
guardrails/<category>/test_<name>.py
guardrails/<category>/fixtures/
collectors/<collector>/collector.json
collectors/<collector>/icon.svg
collectors/<collector>/<collector>.py
collectors/<collector>/test_<collector>.py
collectors/<collector>/fixtures/
collectors/<collector>/example/
lib/
```

`guardrails/` and `collectors/` are sibling namespaces, so a guardrail id never collides with a collector name. `lib/`
holds the Python helper and the test harness. `fixtures/` holds the files a test reads, loaded with
`fixture = fixtures(__file__)`, and a collector's `example/` is the project its documented example runs against.

A category is named for the tool or platform its checks are about, never a theme. Dockerfile checks are `docker`,
Terraform checks are `terraform`, and CODEOWNERS checks sit in both `github` and `gitlab` because the two formats share
no code.

### Bundles

Every category here declares its guardrails in one `guardrails.json` bundle. The bundle carries the `version`, the
`category` and the inputs the whole directory shares. Each entry under `guardrails` is keyed by the last segment of
the id, carries the rest and can override a shared input by name. So `guardrails/git/guardrails.json` declaring
`conventional-commits` is the guardrail `git/conventional-commits`, and `baseRef` is declared once for every
guardrail in the directory that takes one.

The bundle's `icon` names an SVG beside it, drawn in `currentColor` so it follows the reader's theme, and drawn as the
technology's own mark where the category stands for one. It is documentation metadata only. It is optional in the
format, but every bundle in this repository declares one.

A guardrail can also live in a directory of its own, which suits a library holding one guardrail per category:

```
guardrails/<category>/<name>/guardrail.json
guardrails/<category>/<name>/check.py
guardrails/<category>/<name>/test_check.py
```

A reference is looked up in `guardrails/<directory>/guardrails.json` first and in `guardrails/<id>/guardrail.json`
second, so both layouts can sit in one library and a guardrail can move between them without its id changing.

## Writing a guardrail

A guardrail is a bundle entry, a script and a test for that script. The definition format, the script contract and
the Python helper are documented in
[Writing a guardrail](https://docs.buildnote.io/reference/guardrails/writing-guardrails/).

Every guardrail in this repository must:

- declare an `id` matching where it is declared and a `category` matching the first path segment
- ship a script starting with a shebang, run by a supported interpreter
- give every input a default and a description
- carry a `remediation` written as Markdown rather than a bare URL, because it is rendered under the violations in
  the pull request comment
- pass over an empty commit range, and skip rather than fail when its `baseRef` cannot be resolved
- ship a `test_<name>.py` beside its script
- declare only collectors that `collectors/` defines

### Interpreters

The script's extension picks the interpreter: `.py` runs as `python3`, and `.sh` and `.bash` run as `bash`. Any other
extension is rejected when the guardrail loads. A missing interpreter is a skipped verdict with a reason, never a
failure.

Every guardrail here is Python. Python has `json` in its standard library, so building a result never needs `jq`,
which a runner cannot be assumed to have. A shell guardrail is allowed, but it has to build its JSON by hand.

### The Python helper

`guardrail.py` is written beside every check script before it runs, so a check starts with
`from guardrail import Guardrail` and uses it as a context manager. It handles inputs (`input`, `number`), running a
command (`run`) and the result (`violation`, `skip`, `log`, printed on exit).

`run` skips when the executable is not on the runner, because that is missing evidence rather than a violation. It
does not decide what a non-zero exit means: it returns the `CompletedProcess` and the check judges it. Reading a file
is left to the check, which knows whether a missing one is a skip or a violation.

`guardrail_yaml` and `guardrail_toml` are imported the same way. They read the subsets of YAML and TOML the collectors
need, so a runner never has to carry a parser dependency.

The helper always comes from Buildnote itself and is never fetched from the source a guardrail came from, so a
guardrail from any source can use it and a `sha256` pin still covers every file that was fetched. The helper only ever
gains members. A check that imports a member only runs on a Buildnote CLI recent enough to ship it.

Nothing about what a guardrail checks is shared. A check that shells out to `git` does its own preflight in its own
file, and a collector reading SARIF, JUnit or CycloneDX carries its own parser, so reading one script never means
reading a second.

## Collectors

A collector gathers, a guardrail decides. A check reads a JSON document of facts rather than inspecting the
repository itself: every collector the configured guardrails declare runs before the first check, their output is
merged into one facts file named in `GUARDRAIL_FACTS`, and the check reads it with `guardrail.facts("<name>")`. The
facts are attached to the run in Buildnote as `guardrail-facts.json`, so every verdict comes with the evidence it was
decided from.

```json
{
  "collect": ["git"],
  "check": { "run": "conventional-commits.py" }
}
```

`collect` sits on a bundle when the whole category needs the same data, or on an entry when one guardrail does, and the
two are merged.

A collector is a directory holding `collector.json`, its script, an icon and a test. The definition carries an `id`, a
`version`, a `name`, a `description`, an `icon`, the script to `run`, the `scope` it gathers over, a
`timeoutSeconds`, its `inputs`, the collectors it `collect`s from itself, and the `facts` it prints. The `id` must
match the directory name and the `version` the version being resolved, so a collector that moved or was bumped
resolves to nothing rather than to the wrong script.

`facts` is what a guardrail author reads instead of the script: one entry per key the collector prints, keyed by its
path into the document (`head.sha`, `commits[].subject`, `files[path].present`), each saying what it means. `[]`
stands for an entry of a list and `[path]` for a key of a map. A value with nothing declared below it is opaque, which
is how `remotes` and `properties` stay one entry rather than one per key.

| Collector | Facts | Inputs |
|---|---|---|
| `git` | Repository, HEAD, remotes, tags, dirty flag, and every commit in `<baseRef>..HEAD` with its message, author, committer and parents, plus the files the range changed | `baseRef` |
| `gradle` | Settings, manifest, every included project, the wrapper and the distribution it pins, the version catalog, and the direct and transitive dependencies the build files declare and the lock files resolve, versioned by the platforms they declare | `projectDir` |
| `maven` | Root `pom.xml` coordinates, modules, properties and the direct dependencies it and its modules declare, versioned by the BOMs they import | `projectDir` |
| `kotlin` | The Kotlin version declared for the project and for every included project, and the file declaring it | `projectDir` |
| `files` | Presence, size and line counts of well known files, plus a path a guardrail asks for | `paths`, `path` |
| `coverage` | Line and branch coverage from a JaCoCo, lcov, Cobertura or Istanbul report, with per file detail on request | `reports`, `maxFiles`, `lineDetail` |
| `docker` | Every Dockerfile: its stages and base images, whether each is pinned by digest, the user it runs as, and the build argument and environment names it declares | `dockerfiles`, `reports`, `maxFindings` |
| `env` | Which CI provider is running the build, whether the runner is hosted, what triggered it, and whether a federated identity is available | `envFile` |
| `commands` | Every command the build executed, one entry per execution with how long it took and the code it exited with, read from the session a running `buildnote monitor` records, with whether that monitor is still running | `sessionsDir`, `maxExecutions` |
| `provenance` | in-toto and SLSA attestations: predicate type, builder, source, subjects and their digests, and whether each arrived signed | `reports` |
| `sbom` | Components, versions and licences from a CycloneDX or SPDX bill of materials | `reports`, `maxComponents` |
| `scan` | Findings from whatever scanner the build ran, read from SARIF or a Trivy, Grype or OSV report and normalized into one shape | `reports`, `maxFindings` |
| `clojure` | Which build tool the checkout uses, the Clojure version, source paths, aliases, repositories, and every dependency with its alias, origin and whether it is pinned | `projectDir` |
| `cpp` | Which build system and package manager a C or C++ checkout uses, the C++ standard and CMake version it requires, the packages it declares and the ones it expects the machine to carry | `projectDir` |
| `dotnet` | The SDK `global.json` pins, every project file and the frameworks each targets, and the `PackageReference` entries with their central versions | `projectDir`, `maxProjects` |
| `elixir` | The application a Mix project declares, the Elixir version, every application of an umbrella, and the dependency tuples with their environments and origins | `projectDir` |
| `golang` | The module, the Go version and toolchain, every module of a workspace, the direct and indirect requirements, and the replacements | `projectDir` |
| `java` | The Java version the Gradle or Maven build declares, how it declares it, and whether that mechanism makes the build reproducible | `projectDir` |
| `nodejs` | The manifest, the Node version and package manager, every workspace, the dependencies each manifest names with their scopes, and the lock files | `projectDir`, `maxWorkspaces` |
| `php` | The Composer package, the PHP version and extensions it requires, and the packages it requires with their scopes | `projectDir` |
| `python` | The manifest and build backend, the Python version, and the requirements from `[project]`, Poetry, `setup.cfg` or requirements files | `projectDir`, `requirements` |
| `ruby` | The Ruby version, the gem sources, and the gems each manifest declares with their groups and origins | `projectDir` |
| `rust` | The crate, the Rust version and edition, every workspace member, and the dependencies with where each comes from | `projectDir`, `maxMembers` |
| `scala` | The Scala and sbt versions, every subproject, the library dependencies with their configurations, and the plugins the build runs | `projectDir` |
| `secrets` | Secret detector findings, from a report the build left or from gitleaks or trufflehog on the runner. Never the matched secret itself | `reports`, `scanHistory`, `maxFindings` |
| `terraform` | Every Terraform root: its backend, providers and their version constraints, modules, resources, variables and lock file | `directory` |
| `tests` | Test totals and the failing and skipped cases, from a JUnit, NUnit, TRX, CTRF or Open Test Reporting report | `reports`, `maxFailures` |
| `github` | What GitHub reads out of the repository: the Actions workflows, with the events that start them, the token permissions they declare, the runner each job asks for and every action a step uses with how tightly it is pinned; and the CODEOWNERS file, its rules in order and the owners that apply to a path under GitHub's last match wins semantics | `workflows`, `paths` |
| `gitlab` | What GitLab reads out of the repository: the CI pipeline, with its stages and includes and for every job the image and tags it asks for, its timeout and rules and each script section with the variables it interpolates; and the CODEOWNERS file, its sections and whether each is optional or needs several approvals, and the owners that apply to a path in every section that claims it | `pipelines`, `paths` |
| `azure` | Azure Pipelines definitions: what starts a run, the stages and jobs, the pool each job lands on, and every task and script step with the expressions it interpolates | `pipelines` |
| `jenkins` | Jenkinsfiles read by pattern rather than parsed: declarative or scripted, the stages and the steps in them, the timeouts and agents each declares, the shared libraries loaded and how tightly they are pinned | `jenkinsfiles` |

The language collectors share one shape: `directory`, `exists`, `manifest`, `sources`, `declared`, `projects`,
`dependencies.direct` and `unparsed` mean the same thing in each, so a guardrail written against one reads another
with the same code. A manifest that is a program rather than a declaration, such as a `Gemfile`, `mix.exs`,
`build.sbt`, `CMakeLists.txt` or `project.clj`, is read by pattern and listed in that collector's `scanned`. That
means its dependency list is a floor rather than the whole of it.

A collector can `collect` from other collectors rather than gathering the same thing twice, and reads their facts
with `collector.collected("<name>")`. `kotlin` is the worked example: `gradle` and `maven` describe the build, and
`kotlin` is the one place that knows what a Kotlin version looks like in either of them.

A guardrail from another repository can use these collectors too. A collector is looked up in the guardrail's own
source first, at the version that guardrail was asked for, and then among the built-in ones. So `"collect": ["git"]`
works in any guardrail, and a library that wants its own `git` collector ships one beside its guardrails. A `sha256`
pin covers a check script only, not the collectors it asks for.

### Where a collector runs

A collector runs in the directory the check runs in. For a
[policy](https://docs.buildnote.io/reference/guardrails/configuration/#policies), that is each of the `paths` it holds
to account, so a check reads the module it is held to rather than the whole repository.

`"scope": "repository"` says the collector describes the repository rather than a directory of it. It then runs once,
in the directory Buildnote was invoked from, and every path of the policy gets the same facts. `git`, `github`,
`gitlab`, `azure`, `jenkins`, `secrets`, `env`, `scan`, `sbom` and `provenance` declare it: workflows live in
`.github/workflows` whichever module is being checked, and a secret scanner wants the whole repository. A guardrail
whose every collector is repository scoped runs once rather than once per path, so a workflow it faults is reported
once. The default is `"scope": "path"`.

A path scoped collector often still needs what sits above it. A Gradle module has no version catalog, wrapper or
settings of its own. Every collector gets `GUARDRAIL_ROOT_DIR`, the directory Buildnote was invoked from, and
`collector.above("settings.gradle.kts", directory=project_dir)` walks up to the nearest ancestor holding one of the
named files, bounded by that root. Nothing above the checkout is ever read.

A collector that reads from above reports a `root` fact naming the directory it read, or `null` when there was
nothing. Its other facts keep their usual shape: `gradle` folds the root's settings, version catalog, wrapper and
platforms into `settings`, `versionCatalog`, `wrapper` and the dependency versions, `maven` folds the parent POM into
`properties` and the dependency versions, and `kotlin` and `java` fold the root's version into `declared`.
`projects`, `modules` and the dependencies stay those of the directory the collector was asked about.

### Paths in the facts

Every path in the facts is forward-slashed and relative to the directory Buildnote was invoked from, never to the
directory the collector ran in. A Gradle module held to a policy of its own reports `api/build.gradle.kts`, not
`build.gradle.kts`, and the wrapper it inherits reports `gradle/wrapper/gradle-wrapper.properties`, not
`../gradle/wrapper/gradle-wrapper.properties`. A path a check reports as evidence therefore resolves from where the
reader is standing, and no fact ever climbs out of a directory with `..`.

`collector.path(project_dir, *parts)` builds such a path. Apply it only to the value being stored: everything a
collector computes stays relative to its own working directory, because that is what `open`, `os.walk` and a tool's
`cwd` need. `collector.within(stored, *base)` is the inverse, for a collector reading another's facts and needing the
file again, as `kotlin` and `java` do with a manifest `gradle` named.

Two things are deliberately left as they are. A path a third-party report recorded, such as a hadolint finding or a
test case's file, stays exactly as the tool wrote it. And the keys of `files` are the paths the guardrail asked for,
so `files["AGENTS.md"]` means the same thing in every directory; `files[path].location` is where it was looked for.

### Rules for collectors

- **A collector only sees the inputs it declares**, resolved from the guardrail's inputs with its own defaults
  filling the gaps. Facts are collected once per run for each distinct set of inputs, so two guardrails over the same
  range share one collection.
- **A collector has no opinion.** `{"repository": false}` is a fact, not a skip. Every skip belongs to the guardrail.
  A collector that cannot finish calls `invalid(reason)`, which prints what it has with an `incomplete` key.
- **A collector with nothing to say says nothing.** A project that is not a Maven build gets no `maven` key at all:
  the collector calls `nothing(reason)` and its key is left out. A guardrail decides what a missing collector means
  to it, with `facts(name, reason)` to skip in its own words or `optional(name, default)` to treat absence as an
  answer. `files` and `git` are the exceptions, because reporting absence is their job.
- **A collector that fails collects nothing.** A non-zero exit, a timeout or output that is not a JSON object leaves
  its key out, and `facts()` then skips the guardrail with a reason. A failed collector and one with nothing to say
  look the same to a guardrail; only the verbose log tells them apart.

### Tools

A collector may adapt a tool the runner already has, declared under `tools` in `collector.json`:

```json
{
  "tools": {
    "gitleaks": {
      "description": "Secret detector, preferred when no report is present",
      "version": ["--version"],
      "minVersion": "8.0.0",
      "required": false,
      "remediation": "Install with `brew install gitleaks` or add the `gitleaks/gitleaks-action` step"
    }
  }
}
```

Every declared tool is resolved before the collector runs: it is looked up on `PATH`, probed with `version`, and the
result is handed to the script in `GUARDRAIL_TOOLS`:

```json
{"tools": {"gitleaks": {"path": "/usr/local/bin/gitleaks", "version": "8.18.2", "raw": "gitleaks version 8.18.2"}}}
```

A missing tool resolves to `{"path": null, "version": null, "raw": null}`. When a `required` tool is missing the
collector does not run, and the output names the tool and its `remediation`. `minVersion` is recorded, never
enforced; a check that cares reads it and decides.

The script never probes `PATH` itself. `collector.tool("gitleaks")` returns a `Tool` or `None`, and
`Tool.run(*args, timeout=, cwd=, stdin=)` runs it and records the invocation into the facts.

**Buildnote never installs a tool.** A missing tool is missing evidence.

### Reports first, tools second

A collector prefers a report the build already produced and runs a tool only when there is none. Re-running a scanner
costs minutes, and it can give a different answer from the one the pipeline acted on. `collector.reports("*.sarif",
"**/trivy.json")` walks the working directory, skipping `.git`, `node_modules`, `.gradle`, `.terraform` and anything
over 8 MB, and returns `(path, modified, text)` for each match.

Discovery ignores paths that are evidently fixtures: any path with a `fixtures`, `testdata`, `example` or `examples`
segment, and anything under `src/test` or `src/testFixtures`. A scanner report checked in as a test fixture looks
exactly like a real one, and a guardrail passing because it read a fixture is a false clean verdict on a security
control. Pass `fixtures=True` to `reports()` where a collector really means to read them.

Report globs are discovery by default, and an input may only narrow what discovery finds. Facts are cached per
collector and inputs, and only the first document under a collector's name is attached to the run, so two guardrails
asking the same collector for different inputs would each pay for a run and one result would go unseen.

Every tool-backed collector prints a provenance block beside its own facts and declares it in `facts`:

| Path | Meaning |
|---|---|
| `source` | `report` when the facts came from a file the build produced, `tool` when the collector ran one, `none` when there was neither |
| `reason` | Why there was neither, present only when `source` is `none` |
| `reports[]` | Every report that was read, as `{path, modified, format}` |
| `tool.name`, `tool.version`, `tool.path`, `tool.args`, `tool.exitCode`, `tool.durationMs` | The invocation, present only when one was made |

`collector.sourced("report", reports)` sets `source` and `reports`, and `Tool.run` sets `tool`. This block answers
"which scanner, at which version, decided this build was clean".

A collector that found no report and has no tool calls `collector.empty(reason)`, which prints
`{"source": "none", "reason": ...}`. `nothing()` is for a repository the collector does not apply to, not for an
absent tool. Every collector must collect something in its example project.

### Size limits

The merged facts are attached to the run, so they have to stay readable. A collector over 256 KB is logged; one over
2 MB has its contribution replaced by `{"truncated": "<reason>"}`, and `guardrail.facts(name)` turns that into a skip
with the reason. Collect normalized counts, identities and the top N details, and leave the raw report to
`buildnote collect`.

## Testing

Tests use `unittest` from the standard library and need nothing installed. One runs on its own:

```bash
python3 guardrails/git/test_conventional_commits.py
```

Every test in the repository runs with:

```bash
python3 bin/run_tests.py
```

It runs each test file in its own process, several at once, and writes a JUnit report per file to
`build/test-results/`. Pass paths to run only some files, and `--jobs 1` to run them one at a time.

`lib/guardrail_testing.py` is the harness. A test runs its script the way Buildnote does, as a subprocess in a
temporary directory with the `GUARDRAIL_INPUT_*` variables it takes, and asserts on the JSON it prints and the code it
exits with. Nothing is imported from the check, so a check stays a script that runs top to bottom.

- `GuardrailTestCase` names its script in `SCRIPT` and its collectors in `COLLECT`, runs it with
  `check(directory, **inputs)`, builds a workspace or git repository to run against, and asserts with
  `assert_passed`, `assert_skipped` and `assert_violation`.
- `CollectorTestCase` does the same for a collector, with `collect(directory, **inputs)` returning the facts it
  printed.
- `self.rooted_at(dir)` sets `GUARDRAIL_ROOT_DIR`, and `self.skip(reason)` skips a test that finds at runtime it cannot
  assert anything.

A guardrail's test runs the real collectors rather than a fixture of their output, which would drift the moment a
collector renamed a key. Inputs are resolved from `check(...)` and the collector's defaults only, so an input a
guardrail's definition would fill must be passed explicitly.

Collecting anything also checks the facts against the collector's declared `facts`: a path collected but not
declared fails the test, and a path declared but collected by no test in the file fails the file. Documenting a fact
and producing it happen in the same commit.

A collector that runs a tool is tested without that tool installed. `self.shim(name, version=..., stdout=...,
responses=[...])` writes a fake executable answering with canned output, where `responses` is a list of
`[match, stdout, stderr, code]` picked by the arguments. Declared tools resolve only from the shim directory, never
from the real `PATH`, so a test behaves the same whether or not the tool is installed locally. Tools no `tools` block
declares, such as `git`, resolve normally.

Assert the verdict, not just the violation count: a skip prints no violations either. `test_conventional_commits.py`
is the worked example, covering the empty range and an unresolvable `baseRef` alongside the rules themselves.

## License

Apache License 2.0. See [LICENSE](LICENSE). Contributions are accepted under the same license.
