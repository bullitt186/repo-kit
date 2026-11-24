# CI standard

What every repository's CI must contain. The Definition of Done in each repository's
`CONTRIBUTING.md` requires all of it to be green; `AGENTS.md` names the local commands.
Decision: [ADR-0006](adr/0006-ci-standard.md).

## Required on every pull request

| # | Category | What it means | Typical tools |
|---|---|---|---|
| 1 | **Tests** | the full automated test suite, on every supported variant (models, Python versions, platforms) | pytest, vitest/jest, go test, Catch2, cargo test |
| 2 | **Lint and format** | the language's standard linter and a formatter in check mode; style is never argued in review | ruff (lint + format), eslint + prettier, gofmt/golangci-lint, clang-format/clang-tidy, shellcheck, yamllint, markdownlint |
| 3 | **Type check** | where the language has one, in strict mode | mypy --strict, tsc --noEmit, pyright |
| 4 | **Build** | the artefacts the project ships build (firmware, package, image, site) | language build, esphome compile, docker build |
| 5 | **Secret scan** | no credentials enter the history | gitleaks (repo-kit `security` workflow) |
| 6 | **Dependency review** | a pull request adds no dependency with a known high or critical vulnerability | GitHub dependency review (public repos); Forgejo has no diff mode, so Trivy `fs` reports there weekly without blocking |
| 7 | **Static analysis** | security and quality queries on the code | CodeQL default setup (GitHub), Semgrep or the language's analyser (Forgejo) |
| 8 | **PR hygiene** | tests and changelog travel with code, ADR format, scope reference, links | repo-kit `pr-hygiene` |

Coverage is reported with the tests (category 1). A repository may set a minimum that blocks; it
is only ever raised, never lowered to make a change pass. Coverage shows what ran; test strength
is measured by mutation testing, which reports and does not block: surviving mutants in changed
code are handled in review (killed or explained).

## Required on a schedule (do not block pull requests)

| Category | What | Typical tools |
|---|---|---|
| **Mutation testing** | full run weekly, score reported; locally `make mutate` (or the repository's equivalent) on the lines a change touches | mutmut, Stryker, Mull, gremlins |
| **Vulnerability scan** | all dependencies and images against current advisories, weekly; the secret scan covers the full history only here, pull requests and pushes scan their own commits | gitleaks (full history), Trivy, osv-scanner |
| **Dependency updates** | automated update pull requests, weekly, at least 7 days after a release | Dependabot with `cooldown` (GitHub), Renovate with `minimumReleaseAge` (Forgejo) |

## Workflow hardening

- Dependencies are pinned (lockfile or exact versions, images by digest), never `latest`.
- Third-party actions are pinned to a full commit SHA with the version in a comment;
  Dependabot or Renovate keeps the pins current. First-party `actions/*` may use a major tag.
- `permissions:` is set per workflow, `contents: read` by default; a job asks only for what it needs.
- No `pull_request_target` workflow checks out or runs code from the pull request.
- Workflows of outside contributors from forks need maintainer approval before they run; a
  repository with a self-hosted runner requires it for every outside contributor.
- Secrets are never available to pull requests from forks.

## Local equivalents (AGENTS.md "Commands")

Every repository names these commands in the repository part of `AGENTS.md`:

| Row | Purpose |
|---|---|
| Fast check | lint, format check, type check and unit tests; runs in about a minute and is run before **every** commit, also by the agent stop hook |
| Full check | everything CI runs that can run locally (all variants, build); run before opening a pull request when the change can affect it |
| Mutation (changed code) | mutation testing of the lines the change touches |

## Agent stop hook

Repositories worked on with Claude Code register a `Stop` hook in the tracked
`.claude/settings.json` that runs the fast check when the working tree has changes
(`scripts/agent-stop-check.sh`). Instructions alone are skipped; hooks are not.

## Exceptions

A repository that cannot meet a category (for example no type checker for the language, no
build artefact) says so in its `AGENTS.md` under "Rules specific to this repository", with the
reason. A missing category without a reason is a finding in review.
