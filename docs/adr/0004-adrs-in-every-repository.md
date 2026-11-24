# ADR-0004: ADRs in every repository, written by agents and people alike

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

Coding agents start without memory. They need the reasons behind the code in
the repository itself, or they silently reverse earlier decisions.

## Decision

Every repository has `docs/adr/` with an index (`README.md`), a template and
ADR-0001. `AGENTS.md` lists when an ADR is required and makes accepted ADRs
binding. Agents write ADRs in the pull request that implements the decision;
merging accepts it. A decision is changed only by a new ADR that supersedes the
old one. PR hygiene checks file name, title, status, date, the three required
sections and the index entry.

## Consequences

Each significant change carries its reasoning. Repositories with older ADR
formats are migrated once to this format when the kit is applied.

## Alternatives considered

- Lightweight decisions in the changelog: not findable by topic, no status.
- A separate decisions wiki: not versioned with the code, not seen by agents.
