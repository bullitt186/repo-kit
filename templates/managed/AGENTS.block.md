## How to work in this repository (all coding agents)

This block is shared by all repositories of this maintainer and kept in sync by
[repo-kit](https://github.com/bullitt186/repo-kit). Repository-specific
instructions follow below it and win where they are more specific.

A pull request that follows this block passes review without rework. The
maintainer reviews against the same rules: the **Definition of Done** in
`CONTRIBUTING.md`.

### Before you change anything

1. Read this file to the end, `CONTRIBUTING.md`, and the architecture decision
   records in `docs/adr/` (start with `docs/adr/README.md`). An *Accepted* ADR is
   binding: do not work against it. If your change needs a different decision,
   write a new ADR that supersedes it, in the same pull request.
2. Find the issue for the work. If there is none and the change is more than a
   small fix, open one first and describe the problem, not only the solution.
3. Keep one topic per pull request. Do not reformat, rename or refactor code
   that your change does not need.

### Design first

Write the design down before the code: the behaviour that changes, the modules
and interfaces involved, and how it is tested. Put it in the issue or the pull
request description; for a small change the commit message is enough.

Write an ADR (`docs/adr/`, see its README) when the change:

- adds, removes or replaces a runtime dependency or external service,
- changes a public interface: API, CLI, configuration keys, file or data formats,
  entity or topic names, anything users or other systems rely on,
- changes the architecture: module boundaries, data flow, persistence, threading,
- sets a security, privacy or compatibility rule,
- reverses or replaces an earlier ADR.

Bug fixes and refactorings inside existing decisions need no ADR.

### Tests

- A bug fix starts with a regression test that fails for the reason the bug
  describes. Commit it with the fix.
- New behaviour comes with tests. Expected values come from the specification,
  documentation, a protocol table or a recorded real payload, never from running
  the code under test and copying its output.
- Assert observable results (output, state, sent request, raised error), not only
  that something was called.
- Changing an expected value in an existing test needs a reason in the commit
  message that names the source of the new value.
- Do not weaken lint rules, thresholds or checks to make a change pass; fix the
  code. A justified exception gets a comment and a note in the commit message.

### Documentation

Documentation changes in the same pull request as the behaviour it describes:
README, `docs/`, configuration examples, `CHANGELOG.md` (section `[Unreleased]`),
and the ADRs. Outdated documentation counts as a bug. Relative links in Markdown
must point to files that exist.

### Before you open the pull request

- Run the repository's full check (see below) and make it pass. Never commit or
  push on red, never use `--no-verify`.
- Rebase on or merge the current default branch and run the check again.
- Fill in the pull request template completely; tick only what you did.
- No secrets, tokens, personal data, local paths or host names in code, tests,
  logs, commits or pull request text.

### Continuous integration

CI runs the repository's checks and `PR hygiene` from repo-kit. PR hygiene fails
when code changes come without a test change or without a `CHANGELOG.md` entry,
when an ADR is malformed or missing from the index, or when a changed Markdown
file has a broken relative link. Only the maintainer can waive a rule, with the
labels `no-test-change` or `skip-changelog`. Do not ask for a waiver when a test
or changelog entry is possible.

### Respect

Do not change CI configuration, branch protection, release workflows, licence,
or this block unless the issue asks for it. Maintainer decisions recorded in
issues and ADRs are not up for silent change.
