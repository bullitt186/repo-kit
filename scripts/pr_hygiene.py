#!/usr/bin/env python3
"""PR hygiene: the mechanical part of the Definition of Done (repo-kit).

Checks a change set against its base:
  1. code changes come with a test change        (waiver label: no-test-change)
  2. code changes come with a CHANGELOG entry    (waiver label: skip-changelog)
  3. ADRs in docs/adr/ are well-formed and listed in docs/adr/README.md
  4. relative links in changed Markdown files resolve
  5. a change of docs/SCOPE.md comes with an ADR                        (ADR-0007)
  6. code from outside contributors references an issue (Closes #N)
  7. at most max_lines changed lines            (waiver label: large-change)
A release pull request (docs/RELEASING.md) is not a code change: it only bumps the version of
the manifests (and their lockfile's root entry) and moves [Unreleased] under a version heading.

Usage (local):  python3 pr_hygiene.py --base origin/main
Usage (CI):     python3 pr_hygiene.py --base <sha> --labels "a,b"

Per-repository settings in .github/repo-kit.yml (all optional):
  test_paths:     globs of test files       (list)
  exempt_paths:   globs that are not code   (list, added to the defaults)
  changelog:      path, or "none"           (default CHANGELOG.md if it exists)
  max_lines:      changed lines without the large-change label (default 800)
New rules start as warnings and block from their date in ENFORCE_FROM (ADR-0009), so
repositories get time to adapt. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:   # Python 3.10: no TOML parser, so no Python release is recognised (normal rules apply)
    tomllib = None

DEFAULT_TEST = [
    "tests/**", "test/**", "**/tests/**", "**/test/**", "**/__tests__/**",
    "**/test_*", "**/*_test.*", "**/*.test.*", "**/*.spec.*", "**/*_spec.*",
]
DEFAULT_EXEMPT = [
    "**/*.md", "*.md", "docs/**", ".github/**", ".forgejo/**", ".gitea/**", ".claude/**", "LICENSE*", ".gitignore",
    ".gitattributes", ".editorconfig", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.svg",
    "**/*.gif", "**/*.webp", ".pre-commit-config.yaml", ".vscode/**", ".devcontainer/**", "scripts/agent-stop-check.sh", "renovate.json", ".renovaterc*",
    "**/*.example", "*.example", "**/*.example.*", "*.example.*",  # example configuration is documentation
]
ADR_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ADR_STATUS = re.compile(r"^(Proposed|Accepted|Deprecated|Superseded by \[?ADR-\d{4}\]?.*)$")
ADR_SECTIONS = ("## Context", "## Decision", "## Consequences")
# Rule -> first day it blocks; before that it only warns (ADR-0009). Rules not listed block.
ENFORCE_FROM = {
    "scope-adr": "2026-12-15",
    "issue-link": "2026-12-15",
    "size": "2026-12-15",
    "changelog-order": "2026-12-15",
}
# Section order of Keep a Changelog 1.1.0; other headings (e.g. "Upgrade notes") are not checked.
CHANGELOG_SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
LOCKFILES = ["*.lock", "**/*.lock", "**/package-lock.json", "package-lock.json", "**/go.sum", "go.sum",
             "**/pnpm-lock.yaml", "pnpm-lock.yaml", "**/Cargo.lock"]
# Files a dependency update may touch; a pull request labelled `dependencies` (Dependabot,
# Renovate) that changes only these needs no test or changelog change (CI proves it).
DEPENDENCY_FILES = [
    "**/package.json", "package.json", "**/requirements*.txt", "requirements*.txt", "**/pyproject.toml",
    "pyproject.toml", "**/go.mod", "go.mod", "**/Cargo.toml", "Cargo.toml", "**/Dockerfile", "Dockerfile",
    "**/*.lock", "*.lock", "**/package-lock.json", "package-lock.json", "**/pnpm-lock.yaml", "pnpm-lock.yaml",
    "**/go.sum", "go.sum", "**/Gemfile", "Gemfile", "**/composer.json", "composer.json",
]
VERSION_HEADING = re.compile(r"^## \[?v?\d+\.\d+[^\]\s]*\]?(\s.*)?$")
LINK_REFERENCE = re.compile(r"^\[[^\]]+\]:\s*\S+$")   # Keep a Changelog compare links at the bottom
EXTERNAL = {"CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}
ISSUE_REF = re.compile(r"\b(close[sd]?|fix(e[sd])?|resolve[sd]?|refs?)\s+#\d+", re.IGNORECASE)
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def match(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, g) or fnmatch.fnmatchcase(path, g.replace("**/", "")) for g in globs)


def load_config(root: Path) -> dict:
    """Minimal YAML subset: `key: value` and `key:` followed by `- item` lines."""
    cfg: dict = {}
    f = root / ".github" / "repo-kit.yml"
    if not f.exists():
        return cfg
    key = None
    for raw in f.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #")[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and key:
            cfg.setdefault(key, []).append(line.lstrip()[2:].strip().strip("\"'"))
        elif ":" in line:
            key, val = (s.strip() for s in line.split(":", 1))
            if val:
                cfg[key] = val.strip("\"'")
                key = None
    return cfg


def changed_files(base: str, root: Path) -> list[tuple[str, str]]:
    out = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{base}...HEAD"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout
    return [(row.split("\t")[0], row.split("\t")[-1]) for row in out.splitlines() if row.strip()]


def changed_lines(base: str, root: Path) -> dict[str, int]:
    out = subprocess.run(["git", "diff", "--numstat", "--no-renames", f"{base}...HEAD"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    lines: dict[str, int] = {}
    for row in out.splitlines():
        added, removed, path = row.split("\t", 2)
        lines[path] = (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    return lines


def show(rev: str, path: str, root: Path) -> str | None:
    res = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=root, capture_output=True, text=True, check=False)
    return res.stdout if res.returncode == 0 else None


def load(path: str, text: str) -> dict | None:
    """A supported manifest or lockfile, parsed; None if unsupported or unreadable."""
    name = Path(path).name
    try:
        if name in ("package.json", "package-lock.json", "manifest.json"):   # manifest.json: Home Assistant, browser extensions
            data = json.loads(text)
        elif name in ("pyproject.toml", "uv.lock") and tomllib is not None:
            data = tomllib.loads(text)
        else:
            return None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def without_version(path: str, text: str) -> dict | None:
    """The manifest or lockfile without the project's own version fields."""
    data = load(path, text)
    if data is None:
        return None
    try:
        data.pop("version", None)                                     # package.json, package-lock.json, manifest.json
        data.get("packages", {}).get("", {}).pop("version", None)     # package-lock.json root entry
        data.get("project", {}).pop("version", None)                  # pyproject.toml (PEP 621)
        data.get("tool", {}).get("poetry", {}).pop("version", None)   # pyproject.toml (Poetry)
        for pkg in data.get("package", []) if Path(path).name == "uv.lock" else []:
            source = pkg.get("source", {})
            if source.get("editable") == "." or source.get("virtual") == ".":   # the project itself
                pkg.pop("version", None)
    except AttributeError:   # unexpected structure: not a release
        return None
    return data


def is_release_changelog(old: str, new: str) -> bool:
    """New only adds one version heading that takes over the [Unreleased] content."""
    a = [line for line in old.splitlines() if line.strip()]
    b = [line for line in new.splitlines() if line.strip()]
    headings = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if not all(LINK_REFERENCE.match(line) for line in a[i1:i2]):
            return False
        for j in range(j1, j2):
            if VERSION_HEADING.match(b[j]):
                headings.append(j)
            elif not LINK_REFERENCE.match(b[j]):
                return False
    return len(headings) == 1 and headings[0] > 0 and b[headings[0] - 1].startswith("## [Unreleased]")


def is_release(base: str, root: Path, code: list[str], changelog: str) -> bool:
    """Only version fields of manifests changed, and the changelog only gained a version heading."""
    if not code:
        return False
    rev = subprocess.run(["git", "merge-base", base, "HEAD"], cwd=root, capture_output=True, text=True,
                         check=True).stdout.strip()
    bumped = False
    for path in code:
        old, new = show(rev, path, root), show("HEAD", path, root)
        if old is None or new is None:
            return False
        before, after = without_version(path, old), without_version(path, new)
        if before is None or before != after:
            return False
        bumped = bumped or load(path, old) != load(path, new)
    if changelog != "none":
        old, new = show(rev, changelog, root), show("HEAD", changelog, root)
        if old is None or new is None or not is_release_changelog(old, new):
            return False
    return bumped


def check_adrs(root: Path) -> list[str]:
    errors: list[str] = []
    adr_dir = root / "docs" / "adr"
    if not adr_dir.is_dir():
        return errors
    index = adr_dir / "README.md"
    index_text = index.read_text(encoding="utf-8") if index.exists() else ""
    if not index.exists():
        errors.append("docs/adr/README.md (ADR index) is missing")
    seen: dict[str, str] = {}
    for f in sorted(adr_dir.glob("*.md")):
        if f.name in ("README.md", "template.md"):
            continue
        m = ADR_NAME.match(f.name)
        if not m:
            errors.append(f"docs/adr/{f.name}: name must be NNNN-kebab-case-title.md")
            continue
        num = m.group(1)
        if num in seen:
            errors.append(f"docs/adr/{f.name}: number {num} is also used by {seen[num]}")
        seen[num] = f.name
        text = f.read_text(encoding="utf-8")
        if not text.startswith(f"# ADR-{num}: "):
            errors.append(f"docs/adr/{f.name}: first line must be '# ADR-{num}: <title>'")
        status = re.search(r"^- \*\*Status:\*\* (.+)$", text, re.MULTILINE)
        if not status or not ADR_STATUS.match(status.group(1).strip()):
            errors.append(f"docs/adr/{f.name}: needs '- **Status:** Proposed|Accepted|Deprecated|Superseded by ADR-NNNN'")
        if not re.search(r"^- \*\*Date:\*\* \d{4}-\d{2}-\d{2}$", text, re.MULTILINE):
            errors.append(f"docs/adr/{f.name}: needs '- **Date:** YYYY-MM-DD'")
        for sec in ADR_SECTIONS:
            if not re.search(rf"^{re.escape(sec)}\s*$", text, re.MULTILINE):
                errors.append(f"docs/adr/{f.name}: section '{sec}' is missing")
        if f.name not in index_text:
            errors.append(f"docs/adr/{f.name}: not listed in docs/adr/README.md")
    return errors


def check_changelog_order(text: str) -> list[str]:
    """Keep a Changelog sections under [Unreleased] in their standard order, each at most once."""
    m = re.search(r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    found = [h for h in re.findall(r"^### +(.+?)\s*$", m.group(1), re.MULTILINE) if h in CHANGELOG_SECTIONS]
    expected = sorted(dict.fromkeys(found), key=CHANGELOG_SECTIONS.index)
    if found != expected:
        return [f"[Unreleased] sections are {', '.join(found)}; use each once, in the order "
                f"{', '.join(expected)} (Keep a Changelog)"]
    return []


def check_links(root: Path, md_files: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in md_files:
        f = root / rel
        if not f.exists():
            continue
        text = re.sub(r"```.*?```", "", f.read_text(encoding="utf-8"), flags=re.DOTALL)
        for target in MD_LINK.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith(("#", "<")):
                continue
            path = target.split("#")[0]
            if not path:
                continue
            dest = (root / path.lstrip("/")) if path.startswith("/") else (f.parent / path)
            if not dest.exists():
                errors.append(f"{rel}: broken link '{target}'")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="base ref or sha (merge base is used)")
    ap.add_argument("--labels", default="", help="comma-separated pull request labels")
    ap.add_argument("--root", default=".", help="repository root")
    ap.add_argument("--author-association", default="",
                    help="GitHub author_association of the pull request (empty: maintainer)")
    ap.add_argument("--body-file", help="file with the pull request description")
    ap.add_argument("--today", default=dt.date.today().isoformat(), help=argparse.SUPPRESS)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    labels = {lab.strip() for lab in args.labels.split(",") if lab.strip()}
    cfg = load_config(root)

    test_globs = cfg.get("test_paths") or DEFAULT_TEST
    exempt_globs = DEFAULT_EXEMPT + (cfg.get("exempt_paths") or [])
    changelog = cfg.get("changelog", "CHANGELOG.md")
    if changelog != "none" and not (root / changelog).exists():
        changelog = "none"

    files = changed_files(args.base, root)
    paths = [p for _, p in files]
    tests = [p for p in paths if match(p, test_globs)]
    code = [p for st, p in files if st != "D" and p not in tests and not match(p, exempt_globs)
            and not (changelog != "none" and p == changelog)]

    errors: list[str] = []
    warnings: list[str] = []
    if "dependencies" in labels and code and all(match(p, DEPENDENCY_FILES) for p in code):
        code = []   # dependency update: CI is the test, the bot writes the release notes
    if is_release(args.base, root, code, changelog):
        print("PR hygiene: release pull request (version bump and changelog section only)")
        code = []   # docs/RELEASING.md: the release is tested by the full check on the exact commit

    def rule(name: str, message: str) -> None:
        since = ENFORCE_FROM.get(name)
        if since and args.today < since:
            warnings.append(f"{message} (warning; blocks from {since})")
        else:
            errors.append(message)

    if code and not tests and "no-test-change" not in labels:
        errors.append("code changed without a test change: " + ", ".join(code[:8])
                      + (" …" if len(code) > 8 else "")
                      + " (add or update a test; waiver label 'no-test-change' is maintainer-only)")
    if code and changelog != "none" and changelog not in paths and "skip-changelog" not in labels:
        errors.append(f"code changed without an entry in {changelog} under [Unreleased]"
                      " (waiver label 'skip-changelog' is maintainer-only)")
    adr_changed = [p for st, p in files if st != "D" and ADR_NAME.match(Path(p).name) and p.startswith("docs/adr/")]
    if "docs/SCOPE.md" in paths and not adr_changed:
        rule("scope-adr", "docs/SCOPE.md changed without an ADR in docs/adr/ (the scope is a maintainer decision)")
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    if code and args.author_association.upper() in EXTERNAL and not ISSUE_REF.search(body):
        rule("issue-link", "code from a contributor needs a linked issue in the description (Closes #N);"
                      " open one first and wait for the maintainer to mark it 'accepted'")
    max_lines = int(cfg.get("max_lines", 800))
    counted = set(code) | set(tests)   # docs and config do not count towards the size limit
    size = sum(n for p, n in changed_lines(args.base, root).items() if p in counted and not match(p, LOCKFILES))
    if size > max_lines and "large-change" not in labels:
        rule("size", f"{size} changed lines exceed {max_lines}: split the pull request"
                      " (waiver label 'large-change' is maintainer-only)")
    if changelog != "none" and changelog in paths:
        for problem in check_changelog_order((root / changelog).read_text(encoding="utf-8")):
            rule("changelog-order", problem)
    errors += check_adrs(root)
    errors += check_links(root, [p for st, p in files if st != "D" and p.endswith(".md")])

    print(f"PR hygiene: {len(paths)} files changed, {len(code)} code, {len(tests)} test")
    ci = "GITHUB_ACTIONS" in __import__("os").environ
    for w in warnings:
        print(f"::warning::{w}" if ci else f"WARN {w}")
    for e in errors:
        print(f"::error::{e}" if ci else f"FAIL {e}")
    if not errors:
        print("PR hygiene: all checks passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
