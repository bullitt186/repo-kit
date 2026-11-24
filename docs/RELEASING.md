# Release standard

How releases of the maintainer's repositories are prepared and published. Releases, tags and
version numbers are maintainer work; agents prepare them and stop for acceptance.
Decision: [ADR-0008](adr/0008-release-standard.md).

## Versions

- [Semantic Versioning](https://semver.org/): patch for fixes, minor for features (new
  entities, options, models), major for breaking changes.
- Pull requests only add entries under `[Unreleased]` in `CHANGELOG.md`; the version number is
  set in a **release pull request** that moves `[Unreleased]` to the new version and bumps every
  file that carries the version (manifest, package metadata, firmware version).
- A repository that ships every merge (no separate release step) bumps in each pull request
  instead; it records that exception as an ADR.

## Steps

1. **Scope.** List what goes in from the merged changes and what stays out.
2. **Check** the exact commit: full local check and green CI. Earlier results do not count.
3. **Release pull request:** version bump and changelog section, written for users.
4. **Stop: acceptance.** The maintainer accepts the release, usually after the change ran on a
   real installation. Nothing is tagged before that.
5. **Tag** the merge commit of the release pull request after `git fetch`, never a local branch
   that may be stale: `git tag -a vX.Y.Z <merge-sha> -m "vX.Y.Z"`. Check that the version files
   at that commit show `X.Y.Z`. A wrong tag is not moved by an agent; the maintainer fixes it.
6. **Publish** through the release pipeline only. Artefacts (archives, images, firmware) are
   built by CI from the tag, never uploaded from a workstation; images are pinned by digest where
   they are deployed. If users must build themselves (secrets in the build), attach nothing.
7. **Verify** the published artefact as a user gets it: download or install it, check
   signatures where the project signs.
8. **Follow up:** close or update the issues the release solves, and thank reporters and
   contributors there.

## Release notes

The release body is the version's section only, not the whole changelog. Structure:

| Section | Content |
|---|---|
| Summary | two or three sentences for users: what this release brings |
| Thank you | each outside contributor by `@handle`, with what they found, built or tested (and on which device), linked to the issue or pull request |
| What's new | one bold headline per feature, then a plain explanation of what users get |
| Fixes | the symptom users saw, and that it is gone |
| Under the hood | refactorings and internal work in user terms ("behaviour stays the same") |
| Upgrade notes | what users must do: renamed entities or keys, settings to change, statistics to delete; "none" if nothing |
| Full changelog | link to `CHANGELOG.md` or the compare view |

Pre-releases (betas) use the ecosystem's pre-release version format, are published as
pre-release, never as latest, and say so at the top.
