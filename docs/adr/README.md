# Architecture decision records

Decisions that shape this repository, one file each: `NNNN-kebab-case-title.md`,
numbered in order, written from `template.md`. When to write one: `AGENTS.md`.

- An *Accepted* ADR is binding. To change it, add a new ADR and set the old
  one's status to `Superseded by ADR-NNNN`; never rewrite an accepted decision.
- Agents and people write ADRs the same way, in the pull request that implements
  the decision. Merging the pull request accepts the ADR.
- Every ADR is listed in the table below (PR hygiene checks this).

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-central-public-kit-with-managed-blocks.md) | Central public kit with managed blocks | Accepted |
| [0003](0003-pr-hygiene-as-reusable-workflow.md) | PR hygiene as a reusable workflow at a major tag | Superseded by ADR-0005 |
| [0004](0004-adrs-in-every-repository.md) | ADRs in every repository, written by agents and people alike | Accepted |
| [0005](0005-repositories-call-the-stable-branch.md) | Repositories call the stable branch, not a moving tag | Superseded by ADR-0011 |
| [0006](0006-ci-standard.md) | A minimum CI standard for every repository | Accepted |
| [0007](0007-scope-guards-against-drift.md) | Scope guards against changes in the wrong direction | Accepted |
| [0008](0008-release-standard.md) | One release standard | Accepted |
| [0009](0009-lifecycle-pull-grace-scorecard.md) | Kit lifecycle: weekly pull, grace periods, scorecard | Accepted |
| [0010](0010-no-kit-in-forks.md) | No kit in forks of other people's projects | Accepted |
| [0011](0011-callers-pin-the-stable-commit.md) | Callers pin the reusable workflows to the stable commit | Accepted |
