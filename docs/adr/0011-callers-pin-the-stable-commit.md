# ADR-0011: Callers pin the reusable workflows to the stable commit

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

ADR-0005 has the repositories call the reusable workflows at the branch `stable-v2`
(`uses: bullitt186/repo-kit/.github/workflows/<name>-reusable.yml@stable-v2`). CodeQL's default
setup in the repositories reports every such call as `actions/unpinned-tag`, and the CI standard
asks for workflow dependencies pinned to a full commit SHA (#12). Pinning by hand does not last:
the callers are managed files, so the next `kit.py apply` writes `@stable-v2` back, and Dependabot
does not move a SHA that tracks a branch rather than a release tag.

## Decision

We keep `stable-vN` as in ADR-0005: a branch that only moves forward, by fast-forward, to a commit
of `main` with green CI. A change that can turn a passing repository red goes to `stable-v(N+1)`
with an ADR and a new `VERSION` in `kit.py`.

The managed caller workflows pin the reusable workflow to the commit `stable-vN` points to, with
the branch in a comment: `@<40-character SHA> # stable-v2`. The templates hold the placeholder
`{{KIT_SHA}}`; `kit.py apply` and `kit.py update` resolve it with `git ls-remote` against GitHub
(fallback: the local `origin/stable-vN` ref; `REPO_KIT_SHA` overrides both) and write the commit.
The weekly `kit.py update` (ADR-0009) is the bot that moves the pin: when `stable-vN` has moved,
it opens the update pull request. `kit.py check` treats any pinned commit as in sync, so a
repository is not reported as drifted only because `stable-vN` moved since its last update.

Dependabot does not manage these pins: the GitHub seed `dependabot.yml` ignores
`bullitt186/repo-kit*`. Actions the reusable workflows use themselves are pinned to a SHA with
the version in a comment and kept current by this repository's Dependabot.

The PR hygiene script stays on the branch: `hygiene-reusable.yml` checks out repo-kit at
`stable-vN`, so rule fixes and grace dates still reach every repository at once. Within one
`stable-vN` the script's command line stays compatible with every workflow version on that branch.

## Consequences

The `actions/unpinned-tag` alerts for repo-kit's workflows close and a kit sync does not bring
them back. A change to a reusable workflow file reaches a repository only with its next update
pull request (weekly, auto-merged on green CI), not with the fast-forward of `stable-vN`; a fix
to `pr_hygiene.py` still arrives at once. `apply` and `update` need network access to GitHub or
an up-to-date local clone of repo-kit. Repositories set up before this ADR keep their seeded
`dependabot.yml`; whether Dependabot proposes updates for the pinned calls there is unconfirmed
(assumption: it does not, because the pinned commit is not a release tag), and the `ignore` entry
can be copied by hand if it does.

## Alternatives considered

- Release tags (`v2.x.y`) with `@<sha> # v2.x.y` that Dependabot updates: every kit fix needs a
  tag, a protected tag ruleset and a Dependabot pull request in every repository, and the tag
  history duplicates `stable-vN`.
- Declaring repo-kit first party and dismissing the alerts: every new repository and every
  CodeQL re-run needs the dismissal again, and the CI standard would carry an exception.
- Pinning `pr_hygiene.py` to the same commit as the workflow (an input with the ref): a rule fix
  would wait for every repository's update pull request, and grace dates would drift apart.
