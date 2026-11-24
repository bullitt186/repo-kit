# ADR-0005: Repositories call the stable branch, not a moving tag

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

ADR-0003 made the repositories call the reusable workflow at a moving tag `v1`.
Moving a tag means force-pushing it: an operation that cannot be protected by a
ruleset without also blocking the update, and that tooling rightly treats as
destructive. The rest of ADR-0003 holds.

## Decision

`scripts/pr_hygiene.py` checks the mechanical part of the Definition of Done.
GitHub repositories call `.github/workflows/hygiene-reusable.yml@stable` and make
`hygiene / PR hygiene` a required check; Forgejo repositories download the
script from the `stable` branch. `stable` is a branch that only moves forward,
by fast-forward, to a commit of `main` with green CI. A change that can turn a
passing repository red goes to a new branch `stable-v2` with an ADR; the
repositories move to it with `kit.py apply`. Per-repository settings stay in
`.github/repo-kit.yml`, waivers stay maintainer-only labels.

## Consequences

Fixes reach every repository with one fast-forward of `stable`, without force
pushes. A ruleset on `stable` can forbid force pushes and deletion. The tag `v1`
created before this decision is not used.

## Alternatives considered

- Moving tag `v1` (ADR-0003): needs force pushes.
- Fixed version tags per release: every fix needs a pull request in every repository.
- Calling `main`: an unfinished change on `main` would reach every repository at once.
