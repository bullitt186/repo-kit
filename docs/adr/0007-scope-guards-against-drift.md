# ADR-0007: Scope guards against changes in the wrong direction

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

Checks make sure a change is built right, not that it is the right change. Coding agents make
large, well-tested pull requests cheap, so a contribution can add features nobody asked for or
pull a project in another direction while passing every quality check.

## Decision

Each repository has `docs/SCOPE.md` with purpose, in scope, out of scope, direction and
principles. It is binding like an accepted ADR: changing it needs an ADR in the same pull request
(PR hygiene). Features start as an issue; the maintainer marks fitting ones `accepted` or closes
them `out-of-scope`. Code pull requests from outside contributors must reference their issue
(PR hygiene, GitHub `author_association`). Pull requests above `max_lines` changed code and test
lines (default 800) need the maintainer's `large-change` label. The Definition of Done starts
with "fits the scope", and the maintainer's review checks the linked issue is `accepted`.

## Consequences

Contributors learn before they build whether their idea fits. Small fixes and documentation stay
frictionless. Ideas outside the scope can still be proposed, as an issue or an ADR that changes
the scope, but not slipped in. Forgejo does not report an author association, so the issue rule
applies there through review only.

## Alternatives considered

- Review alone: works for people, but agents produce plausible large changes faster than review
  can push back.
- CODEOWNERS approval for all paths: every pull request needs the maintainer anyway; it adds no
  signal about direction.
