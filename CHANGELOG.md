# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [Unreleased]

### Added

- `kit.py update` opens the pull request on Forgejo too (with `FORGEJO_API` set) and sets
  "merge when checks succeed" when there are no findings.
- `kit.py forgejo`: labels and default-branch protection on Forgejo (required checks PR hygiene and
  secret scan on merge, no force push or deletion; direct pushes stay possible for CI that commits).

### Fixed

- `kit.py update` reports a failing commit or push (for example a pre-commit hook that needs the
  repository's dev environment) as a finding for an agent instead of crashing; hooks are never bypassed.
- `kit.py score` treats an older pinned kit commit as in sync, like `check`.
- Managed caller workflows pin repo-kit's reusable workflows to the commit of `stable-v2`
  (`@<sha> # stable-v2`) instead of the branch, which CodeQL reported as `actions/unpinned-tag`
  in every repository (#12, ADR-0011). `kit.py apply` and the weekly `kit.py update` move the pin;
  `kit.py check` accepts any pinned commit. The GitHub seed `dependabot.yml` ignores these pins,
  and `hygiene-reusable.yml` pins `actions/checkout` to a SHA.
- Forgejo security workflow: a push scans only the pushed commits (it scanned the whole history and
  turned `main` red for old findings); the full history and the Trivy report run weekly.
- `renovate.json` is not code for PR hygiene.
- Secret scan on pull requests of private repositories failed with HTTP 403: the reusable
  workflow now grants the job `pull-requests: read` (#9).
- `kit.py github` no longer enables CodeQL default setup in repositories with their own CodeQL
  workflow; GitHub would then reject the workflow's uploads.

### Added

- Forgejo seed `renovate.json` (7 days minimum release age, label `dependencies`).
- PR hygiene accepts dependency updates labelled `dependencies` (Dependabot, Renovate) that only touch
  manifests and lockfiles without a test or changelog change.
- Kit lifecycle (ADR-0009): `kit.py update` (weekly pull into a dated update branch and pull
  request), `kit.py score` and `kit.py scorecard` (traffic light per discipline, trend), grace
  periods for new PR hygiene rules (the scope, issue-link and size rules warn until 2026-12-15).
- `kit.py apply` refuses forks of other people's projects unless `--own-product` (ADR-0010).
- `ci_exceptions` in `.github/repo-kit.yml`; this repository lints with ruff in CI.

### Upgrade notes

- Kit v2 runs on the branch `stable-v2`. Repositories move with `kit.py apply` (the managed
  workflows then call the commit of `stable-v2`, ADR-0011) and fill the new placeholders `kit.py check` reports
  (`docs/SCOPE.md`, `scripts/agent-stop-check.sh`, the fast/full/mutation rows in `AGENTS.md`).
  Repositories that do not re-apply stay on `stable` (v1) unchanged.

### Added

- Scope guards (ADR-0007): `docs/SCOPE.md` seed; PR hygiene requires an ADR for scope changes,
  an issue reference for code from outside contributors, and the `large-change` label above 800
  changed lines of code and tests; labels `accepted`, `out-of-scope`, `large-change`.
- CI standard (ADR-0006, `docs/CI_STANDARD.md`) with a managed `security` workflow (gitleaks,
  dependency review; on Forgejo gitleaks and a Trivy report), Dependabot seed with cooldown, agent
  stop hook seed, and security settings in `kit.py github`.
- Release standard (ADR-0008, `docs/RELEASING.md`).

### Changed

- The shared `AGENTS.md` block wins over repository-specific text unless an ADR records the
  exception; it now covers issue-first work, small fixes, mutation testing, deterministic tests,
  commits and branches, Forgejo issue references, changelog style and watching CI.
- The Definition of Done starts with "fits the scope"; the pull request template is managed by the
  kit (v1 copies are upgraded) and checks scope fit.
- `kit.py` keeps a repository's own version of a managed file and reports it as "custom".

### Added

- Forgejo repositories (origin not on github.com) get `.forgejo/workflows/pr-hygiene.yml`, which runs the check from `stable` on the `light` runner.

- `kit.py apply | check | github`, managed `AGENTS.md` and `CONTRIBUTING.md` blocks with the
  Definition of Done, seed templates (pull request, issue forms, ADR folder, changelog).
- `pr_hygiene.py` and the reusable workflow `hygiene-reusable.yml` (`@stable`, ADR-0005).

