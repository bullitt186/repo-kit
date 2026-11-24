# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [Unreleased]

### Added

- Forgejo repositories (origin not on github.com) get `.forgejo/workflows/pr-hygiene.yml`, which runs the check from `stable` on the `light` runner.

- `kit.py apply | check | github`, managed `AGENTS.md` and `CONTRIBUTING.md` blocks with the
  Definition of Done, seed templates (pull request, issue forms, ADR folder, changelog).
- `pr_hygiene.py` and the reusable workflow `hygiene-reusable.yml` (`@stable`, ADR-0005).

