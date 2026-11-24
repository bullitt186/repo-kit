# ADR-0003: PR hygiene as a reusable workflow at a major tag

- **Status:** Superseded by ADR-0005
- **Date:** 2026-11-24

## Context

Rules that are only written down are skipped, by agents as well as people.
The mechanical part of the Definition of Done (tests and changelog travel with
code, ADR format and index, working links) can be checked on every pull
request. Repositories on the free plan can call reusable workflows only from
public repositories.

## Decision

`scripts/pr_hygiene.py` checks these rules using the standard library only.
Each repository calls `.github/workflows/hygiene-reusable.yml@v1` from a small
managed workflow and makes the check `hygiene / PR hygiene` required in its
ruleset. Settings per repository live in `.github/repo-kit.yml`. The maintainer
waives a rule with the labels `no-test-change` or `skip-changelog`; contributors
cannot set labels, so a waiver is always a maintainer decision.

## Consequences

Fixes to the check reach all repositories by moving the `v1` tag. A stricter
check that can turn passing repositories red needs `v2`. The check cannot judge
test quality or whether documentation is complete; that stays in review.

## Alternatives considered

- Copy the script into every repository: drifts, and fixes need a pull request each.
- A third-party danger-style bot: extra dependency and token handling for little gain.
