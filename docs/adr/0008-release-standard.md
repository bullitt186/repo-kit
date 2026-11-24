# ADR-0008: One release standard

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

Releases were prepared differently per repository: version bumps in every commit or in a release
pull request, release bodies with the whole changelog or one section, contributor thanks
sometimes forgotten. The best practice already existed in single repositories: a release pull
request, tagging the fetched merge commit, acceptance before tagging, artefacts only from the
pipeline, and release notes with summary, thanks, what's new, fixes, "under the hood" and upgrade
notes.

## Decision

`docs/RELEASING.md` is the release standard for all repositories. Pull requests only add
`[Unreleased]` entries written for users; a release pull request sets the version; the maintainer
accepts before the tag; artefacts come from CI; release notes follow the section table there.
Repositories that ship every merge bump per pull request and record that as an ADR.

## Consequences

Contributors and agents never touch version numbers in normal pull requests, which removes a
common merge conflict. Release notes look the same everywhere and always credit contributors.

## Alternatives considered

- Version bump in every fix or feature commit: conflicts between parallel pull requests and
  versions nobody released.
- Generated release notes from commit titles: miss the user perspective and the thanks.
