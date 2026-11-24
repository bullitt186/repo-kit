# ADR-0002: Central public kit with managed blocks

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

The maintainer has many repositories, and many contributors work with coding
agents. Rules copied by hand into each repository drift apart, and an agent
cannot follow rules it cannot read. Each repository also has its own commands
and constraints that a shared file cannot know.

## Decision

We keep the shared rules in this public repository and copy them into each
repository with `kit.py apply`. Shared text sits between `repo-kit` markers in
`AGENTS.md` and `CONTRIBUTING.md` and is refreshed on every apply; text outside
the markers belongs to the repository. Files a repository adapts (templates,
changelog, ADR index) are seeded once and never overwritten. The Definition of
Done in `CONTRIBUTING.md` is the single list that agents, contributors and the
maintainer's review use.

## Consequences

Every repository works offline and is readable without this repository, and a
kit update is one `apply` plus a pull request per repository. `kit.py check`
finds drift. The shared block must stay generic.

## Alternatives considered

- A template repository: only helps new repositories, not existing ones.
- Git submodule or symlinks: agents and GitHub do not follow them reliably.
- Rules only in the maintainer's private notes: contributors' agents cannot read them.
