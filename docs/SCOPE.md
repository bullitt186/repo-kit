# Scope

What this project is for, so contributions go in the same direction. Changing this file is a
maintainer decision, recorded as an ADR in the same pull request (PR hygiene checks this).

## Purpose

repo-kit gives every repository of one maintainer the same contributor and coding-agent setup:
what to read, how to work, what "done" means, and checks that hold people and agents to it.

## In scope

- Shared instruction blocks (`AGENTS.md`, `CONTRIBUTING.md`) and seed templates
- Checks that can be evaluated mechanically on a pull request (PR hygiene, security workflow)
- Configuration of the maintainer's forges (GitHub, Forgejo) for these rules
- Standards that repositories implement themselves (CI, releases)

## Out of scope

- Language- or framework-specific CI: each repository knows its toolchain best
- A general-purpose tool for other maintainers: no options or plugin system for other conventions
- Hosting or running CI, bots that comment or merge
- Anything personal or site-specific: hosts, people, private repositories

## Direction

Close the gaps the maintainer's review still finds by hand, one check or rule at a time, and
keep the blocks short enough that agents read them completely.

## Principles

- One rule, one place: the Definition of Done is the only list; everything else points to it.
- Enforce what can be checked; describe only what needs judgement.
- Standard library only for the scripts, so every repository can run them without installing.
- Never break passing repositories silently: breaking changes go to a new `stable-vN` branch.
