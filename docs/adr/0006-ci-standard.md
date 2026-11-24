# ADR-0006: A minimum CI standard for every repository

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

The Definition of Done says "all CI checks green", but what CI must contain differed per
repository: some ran linters, type checks, secret scans and mutation testing, others only tests
or nothing. A green CI therefore meant different things, and contributor agents could not know
what quality bar applied. Some repositories already showed a good pattern (pinned actions,
gitleaks, CodeQL, dependency review, weekly mutation runs).

## Decision

`docs/CI_STANDARD.md` defines the categories every repository's CI covers: on every pull
request tests, lint and format, type check, build, secret scan, dependency review, static
analysis and PR hygiene; on a schedule mutation testing, a full vulnerability scan and dependency
updates; plus workflow hardening rules. repo-kit ships what is generic: a managed `security`
workflow (gitleaks, dependency review on GitHub; gitleaks and Trivy on Forgejo), CodeQL default
setup, secret scanning with push protection and fork-workflow approval via `kit.py github`, a
Dependabot seed and an agent stop hook seed. Language-specific checks stay in each repository's
own CI; `AGENTS.md` names their local commands (fast check, full check, mutation). A category a
repository cannot meet is listed with its reason in `AGENTS.md`.

## Consequences

Green CI means the same everywhere. Repositories with known vulnerable dependencies turn red
until they update or record a justified ignore. A repository with its own security workflow keeps
it (`kit.py check` reports it as "custom") as long as it covers the same categories.

## Alternatives considered

- One reusable CI for all languages: cannot know each project's toolchain.
- Only recommendations: what is not enforced is skipped, by agents first.
