# ADR-0009: Kit lifecycle: weekly pull, grace periods, scorecard

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

The kit will keep changing, and every change has to reach all repositories that use it. Letting
an agent re-check every repository is slow and expensive; most of an update is mechanical. New
rules must not block ongoing work the day they ship, and the maintainer wants to see at a glance
how far each repository meets the standard, without keeping a register of repositories by hand.

## Decision

- **Pull, discovered, not pushed from a register.** A weekly run on the maintainer's machine
  fetches every local clone, keeps those whose default branch carries the `repo-kit` block, and
  runs `kit.py update` from the newest released `stable-vN` branch: a throwaway worktree, `apply`,
  and if anything changed a dated branch `chore/repo-kit-update-YYYYMMDD` with a pull request
  (GitHub: auto-merge when CI is green). An agent is only involved when `kit.py check` reports
  findings that need judgement. Contributors never run it.
- **Grace periods.** A new PR hygiene rule gets a date in `ENFORCE_FROM`; before it, the rule
  only warns on the pull request. PR hygiene already judges only the files a pull request
  changes, so existing code is never forced into a refactoring by a new rule.
- **Scorecard.** `kit.py score` rates a repository per discipline of the standard (instructions,
  scope, ADRs, PR hygiene, security, updates, stop hook, tests, lint, types, mutation) as
  green, yellow, red or n/a (exception with reason in `.github/repo-kit.yml` `ci_exceptions`).
  The weekly run writes one table for all repositories into the maintainer's notes, with the
  trend against the previous week; a drop becomes a task. Nothing is committed to the
  repositories.

## Consequences

Kit updates cost one merged pull request per repository and week at most, usually without an
agent. The score is a heuristic (it looks for tool names in CI and build files); exceptions are
explicit and reviewable. A repository joins the update and the scorecard simply by adopting the
kit, and leaves by removing it.

## Alternatives considered

- A bot workflow in every repository: pull requests opened with the workflow token start no CI,
  and Forgejo needs a second implementation.
- A central list of kit repositories: one more thing to keep in sync.
- A scorecard file committed by CI in each repository: commit noise and merge conflicts.
- Per-repository opt-in for new rules: more state and more drift than a date per rule.
