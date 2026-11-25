# repo-kit

One consistent setup for contributors and coding agents across all repositories
of [@bullitt186](https://github.com/bullitt186): what to read, how to work, what
"done" means, and checks that hold everyone to it.

If you contribute to one of those repositories, you do not need this repository:
read `AGENTS.md` and `CONTRIBUTING.md` in the repository you work on. This is
where those shared parts come from.

## What a repository gets

| File | Owner | Purpose |
|---|---|---|
| `AGENTS.md` | shared block + repository part | how agents (and people) work: scope and ADRs first, design, tests, docs, commits, checks |
| `CLAUDE.md` | seed | `@AGENTS.md`, so Claude Code reads the same rules |
| `CONTRIBUTING.md` | repository part + shared block | the **Definition of Done** and labels; the maintainer reviews against it |
| `.github/pull_request_template.md` | managed | the Definition of Done as a checklist |
| issue forms | seed | structured reports; feature requests ask how they fit the scope |
| `docs/SCOPE.md` | seed | purpose, in scope, out of scope, direction, principles; changes only with an ADR |
| `docs/adr/` | seed | architecture decision records: index, template, ADR-0001 |
| `CHANGELOG.md` | seed | Keep a Changelog, `[Unreleased]` section |
| `.github/workflows/pr-hygiene.yml` | managed | calls the reusable check below |
| `.github/workflows/security.yml` | managed | secret scan and dependency review (GitHub); secret scan and Trivy report (Forgejo, under `.forgejo/`) |
| `.github/dependabot.yml` | seed (GitHub) | weekly updates with a 7-day cooldown |
| `renovate.json` | seed (Forgejo) | updates through the self-hosted Renovate, 7 days minimum release age, label `dependencies` |
| `.claude/settings.json`, `scripts/agent-stop-check.sh` | seed | stop hook that runs the fast check before an agent finishes |
| `.github/repo-kit.yml` | seed | per-repository settings of the check |

*Shared block*: text between `repo-kit` markers, refreshed by `kit.py apply`.
*Seed*: created when missing, then owned by the repository. *Managed*: owned by
the kit, overwritten on apply.

## PR hygiene

`scripts/pr_hygiene.py` checks the mechanical part of the Definition of Done on
every pull request:

1. code changes come with a test change (waiver label `no-test-change`),
2. code changes come with a `CHANGELOG.md` entry (waiver label `skip-changelog`),
3. ADRs are well-formed (name, title, status, date, Context/Decision/Consequences)
   and listed in `docs/adr/README.md`,
4. relative links in changed Markdown files resolve,
5. a change of `docs/SCOPE.md` comes with an ADR,
6. code from outside contributors references an issue (`Closes #N`),
7. at most 800 changed lines of code and tests (waiver label `large-change`).

Waiver labels can only be set by the maintainer. A release pull request
([release standard](docs/RELEASING.md)) needs none: when it only bumps the version of
`pyproject.toml` or `package.json` (and the project's entry in `package-lock.json` or `uv.lock`)
and moves `[Unreleased]` under a new version heading, it is not a code change. Run it locally
before you push:

```bash
curl -fsSL https://raw.githubusercontent.com/bullitt186/repo-kit/stable-v2/scripts/pr_hygiene.py \
  | python3 - --base origin/main
```

Settings (`.github/repo-kit.yml`): `test_paths` (globs, replace the defaults),
`exempt_paths` (globs that are not code, added to the defaults), `changelog`
(path or `none`), `max_lines` (default 800).

## Standards

- [CI standard](docs/CI_STANDARD.md): what every repository's CI covers (tests, lint, types,
  build, secret scan, dependency review, static analysis, PR hygiene; mutation and scans weekly).
- [Release standard](docs/RELEASING.md): versions, release pull request, acceptance, tagging,
  release notes.

## Maintainer use

```bash
python3 scripts/kit.py apply  ../some-repo     # add missing files, refresh shared blocks
python3 scripts/kit.py check  ../some-repo     # drift, unfilled TODOs, missing stop hook -> exit 1
python3 scripts/kit.py github owner/some-repo --checks "Tests,Lint"   # settings, labels, rulesets
python3 scripts/kit.py forgejo owner/some-repo --api https://forge.example/api/v1   # labels, protection
python3 scripts/kit.py score  ../some-repo     # traffic light per discipline of the standard
python3 scripts/kit.py update ../some-repo     # weekly pull: dated update branch and pull request
```

`github` sets squash merge with branch deletion and auto-merge, creates the
labels from `CONTRIBUTING.md` (including `dependencies`, which the Dependabot and
Renovate seeds set and PR hygiene relies on), makes the workflow token read-only, enables
Dependabot alerts and security updates, and requires approval for outside
contributors' workflows unless the repository chose otherwise. On public
repositories it also enables secret scanning with push protection, CodeQL
default setup and private vulnerability reporting, and creates a ruleset for the
default branch (pull request required, resolved threads, required checks
including `hygiene / PR hygiene` and the security checks, no force push or
deletion) and one that protects `v*` tags. Existing rulesets are kept; missing
checks are added.

`forgejo` creates the same labels on Forgejo; Renovate silently drops a label
that does not exist there. `score` turns `updates` yellow when origin's
repository lacks the `dependencies` label; it reads the labels with `gh` on
GitHub and, on Forgejo, only when `FORGEJO_API` and a token are set (otherwise it
gives no verdict on the label).

Releasing the kit: after a change is merged and CI on `main` is green,
fast-forward the branch the repositories use: `git push origin main:stable-v2`
(never forced; see [ADR-0005](docs/adr/0005-repositories-call-the-stable-branch.md)).
The callers pin the reusable workflows to the commit of `stable-v2`
([ADR-0011](docs/adr/0011-callers-pin-the-stable-commit.md)), so a changed workflow file reaches a
repository with its next weekly `kit.py update` pull request; `pr_hygiene.py` follows the branch.

New repository: create it, run `apply`, fill in the repository part of
`AGENTS.md` (purpose, layout, commands), commit through a pull request, then
run `github` with the names of its CI checks.

## Lifecycle

- **Pull, not push** ([ADR-0009](docs/adr/0009-lifecycle-pull-grace-scorecard.md)): a weekly run
  finds every clone whose default branch carries the kit block and runs `kit.py update` from the
  newest `stable-vN`. Changes arrive as a pull request `chore: repo-kit update`; an agent is only
  needed for findings that need judgement.
- **Grace periods:** new PR hygiene rules warn until their date in `ENFORCE_FROM`, then block.
  Only changed files are judged, so new rules never force a refactoring of existing code.
- **Scorecard:** `kit.py score` per repository; the weekly run collects one table with the
  trend. Exceptions to the CI standard go into `.github/repo-kit.yml`:
  `ci_exceptions: ["types: <reason>"]`.
- **Breaking kit changes** go to the next `stable-vN` branch ([ADR-0005](docs/adr/0005-repositories-call-the-stable-branch.md)).

## Forks

The kit is not applied to forks of other people's projects
([ADR-0010](docs/adr/0010-no-kit-in-forks.md)); `kit.py apply` refuses them. Their upstream's rules
apply; personal agent notes go into an untracked `CLAUDE.local.md`. A fork that became your own
product records that in an ADR and uses `--own-product`.

## Decisions

See [docs/adr](docs/adr/README.md).

## Licence

MIT, see [LICENSE](LICENSE).
