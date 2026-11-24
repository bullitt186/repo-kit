# ADR-0010: No kit in forks of other people's projects

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

A fork belongs to another maintainer's project, with their own rules. Bringing the kit's files
and way of working into it makes every contribution back upstream carry unrelated changes, or
forces a cleanup before each upstream pull request.

## Decision

`kit.py apply` refuses forks: a GitHub repository marked as fork, or a clone with an `upstream`
remote. In such repositories the upstream's rules apply; the maintainer's own notes for agents go
into an untracked `CLAUDE.local.md` (read by Claude Code, never committed). If a fork has become
the maintainer's own product with no intention to merge back, an ADR there records that, and the
kit is applied with `--own-product`.

## Consequences

Forks stay clean for upstream pull requests. Agents in forks follow the upstream project's
`CONTRIBUTING.md` and the maintainer's global instructions, not the kit.

## Alternatives considered

- The kit on a separate long-lived branch of the fork: every upstream sync becomes a merge of
  two ways of working.
