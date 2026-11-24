#!/usr/bin/env python3
"""repo-kit: one consistent contributor and agent setup for every repository.

  kit.py apply  <repo-dir>             add missing files, refresh managed blocks
  kit.py check  <repo-dir>             report drift from the kit (exit 1 on drift)
  kit.py github <owner/repo> [--checks "Name A,Name B"] [--dry-run]
                                       repository settings, labels, rulesets

File classes (templates/):
  managed/*.block.md   block between repo-kit markers in AGENTS.md / CONTRIBUTING.md,
                       refreshed on every apply; text outside the markers is the repo's own
  managed/<path>       whole file owned by the kit, overwritten on apply
  seed/<path>          created when missing, never overwritten
Standard library only; `github` needs an authenticated `gh` CLI.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
TEMPLATES = KIT / "templates"
VERSION = "2"
BEGIN = f"<!-- repo-kit:begin v{VERSION} (managed, do not edit; https://github.com/bullitt186/repo-kit) -->"
END = "<!-- repo-kit:end -->"
BLOCKS = {"AGENTS.md": "AGENTS.block.md", "CONTRIBUTING.md": "CONTRIBUTING.block.md"}

LABELS = {
    "needs-info": ("d4c5f9", "Waiting for information from the reporter"),
    "needs-hardware": ("fbca04", "Needs a test on a device or system the maintainer does not have"),
    "blocked": ("b60205", "Waits for another issue or pull request"),
    "decision": ("5319e7", "Needs a maintainer decision"),
    "breaking": ("d93f0b", "Changes behaviour users rely on"),
    "adr": ("0e8a16", "Adds or changes an architecture decision record"),
    "no-test-change": ("c5def5", "Maintainer waiver: PR hygiene test rule"),
    "skip-changelog": ("c5def5", "Maintainer waiver: PR hygiene changelog rule"),
    "accepted": ("0e8a16", "In scope; a pull request is welcome (set by the maintainer)"),
    "out-of-scope": ("ededed", "Does not fit docs/SCOPE.md"),
    "large-change": ("c5def5", "Maintainer waiver: PR hygiene size rule"),
    "bug": ("d73a4a", "Something does not work as documented"),
    "enhancement": ("a2eeef", "New feature or request"),
}
HYGIENE_CHECK = "hygiene / PR hygiene"
SECURITY_CHECKS = ["security / Secret scan", "security / Dependency review"]


def block_text() -> dict[str, str]:
    return {f: f"{BEGIN}\n{(TEMPLATES / 'managed' / t).read_text(encoding='utf-8').rstrip()}\n{END}"
            for f, t in BLOCKS.items()}


def replace_block(text: str, block: str) -> str | None:
    """Text with the managed block replaced, or None if there is no block."""
    start = text.find("<!-- repo-kit:begin")
    end = text.find(END, start)
    if start < 0 or end < 0:
        return None
    return text[:start] + block + text[end + len(END):]


def forge(repo: Path) -> str:
    """'github' when origin is on github.com or there is no origin, else 'forgejo'."""
    r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo, capture_output=True, text=True)
    return "github" if r.returncode != 0 or "github.com" in r.stdout else "forgejo"


MANAGED_MARK = "Managed by repo-kit"
# Files the kit wrote as seeds in v1 and manages since v2 (recognised by their first line).
V1_MARKS = ("<!-- Definition of Done: CONTRIBUTING.md. Tick only what you did",)


def kit_owned(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return MANAGED_MARK in text or any(text.startswith(m) for m in V1_MARKS)


def managed_files(repo: Path) -> dict[Path, str]:
    """Whole files the kit owns for this repository's forge."""
    managed = TEMPLATES / ("managed-forgejo" if forge(repo) == "forgejo" else "managed")
    return {repo / p.relative_to(managed): p.read_text(encoding="utf-8")
            for p in sorted(managed.rglob("*")) if p.is_file() and not p.name.endswith(".block.md")}


def findings(repo: Path) -> list[str]:
    """Things a repository must fix by hand: placeholders, custom files, missing stop hook."""
    out = []
    for rel in ("AGENTS.md", "docs/SCOPE.md", "scripts/agent-stop-check.sh"):
        f = repo / rel
        if f.exists() and "TODO" in f.read_text(encoding="utf-8"):
            out.append(f"todo   {rel} has unfilled TODO placeholders")
    for path in managed_files(repo):
        if path.exists() and not kit_owned(path):
            out.append(f"custom {path.relative_to(repo)} is the repository's own (kept); "
                       "it must cover what the kit's version checks (docs/CI_STANDARD.md)")
    settings = repo / ".claude" / "settings.json"
    if settings.exists() and "agent-stop-check" not in settings.read_text(encoding="utf-8"):
        out.append("hook   .claude/settings.json has no Stop hook running scripts/agent-stop-check.sh")
    return out


def planned(repo: Path) -> dict[Path, str]:
    """Target content for every file the kit wants to write in repo."""
    out: dict[Path, str] = {}
    blocks = block_text()
    today = dt.date.today().isoformat()
    for path in sorted((TEMPLATES / "seed").rglob("*")):
        if path.is_file() and path.name != "AGENTS.repo.md":
            rel = path.relative_to(TEMPLATES / "seed")
            if str(rel).startswith("docs/adr/0001") and any((repo / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
                continue   # existing ADRs keep their own numbering
            if not (repo / rel).exists():
                out[repo / rel] = path.read_text(encoding="utf-8").replace("{{DATE}}", today)
    for kind in ("seed-github",) if forge(repo) == "github" else ():
        for path in sorted((TEMPLATES / kind).rglob("*")):
            rel = path.relative_to(TEMPLATES / kind)
            if path.is_file() and not (repo / rel).exists():
                out[repo / rel] = path.read_text(encoding="utf-8")
    for path, content in managed_files(repo).items():
        if not path.exists() or kit_owned(path):
            out[path] = content
    # AGENTS.md: block on top, repository part below
    agents = repo / "AGENTS.md"
    if agents.exists():
        cur = agents.read_text(encoding="utf-8")
        new = replace_block(cur, blocks["AGENTS.md"])
        if new is None:
            head, _, rest = cur.partition("\n") if cur.startswith("# ") else ("# AGENTS.md", "", cur)
            new = f"{head}\n\n{blocks['AGENTS.md']}\n\n{rest.lstrip()}"
        out[agents] = new
    else:
        repo_part = (TEMPLATES / "seed" / "AGENTS.repo.md").read_text(encoding="utf-8")
        out[agents] = f"# AGENTS.md\n\n{blocks['AGENTS.md']}\n\n{repo_part}"
    # CONTRIBUTING.md: repository part on top, block at the end
    contrib = repo / "CONTRIBUTING.md"
    if contrib.exists():
        cur = contrib.read_text(encoding="utf-8")
        new = replace_block(cur, blocks["CONTRIBUTING.md"])
        out[contrib] = new if new is not None else f"{cur.rstrip()}\n\n{blocks['CONTRIBUTING.md']}\n"
    else:
        out[contrib] = ("# Contributing\n\nThanks for helping. Coding agents and people follow the same "
                        "rules: read [AGENTS.md](AGENTS.md) before you start.\n\n"
                        f"{blocks['CONTRIBUTING.md']}\n")
    # CLAUDE.md must load AGENTS.md
    claude = repo / "CLAUDE.md"
    if claude.exists():
        cur = claude.read_text(encoding="utf-8")
        if "@AGENTS.md" not in cur:
            out[claude] = f"@AGENTS.md\n\n{cur}"
    return {p: c for p, c in out.items() if not p.exists() or p.read_text(encoding="utf-8") != c}


def cmd_apply(repo: Path) -> int:
    for path, content in planned(repo).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(repo)}")
    return 0


def cmd_check(repo: Path) -> int:
    drift = planned(repo)
    for path in drift:
        print(f"drift  {path.relative_to(repo)}")
    found = findings(repo)
    for f in found:
        print(f)
    blocking = [f for f in found if not f.startswith("custom")]
    print("in sync" if not drift and not blocking else
          f"{len(drift)} file(s) differ from repo-kit v{VERSION}, {len(blocking)} finding(s)")
    return 1 if drift or blocking else 0


def gh(*args: str, data: dict | None = None, check: bool = True) -> dict | list | None:
    cmd = ["gh", "api", *args]
    if data is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=json.dumps(data) if data is not None else None,
                       capture_output=True, text=True)
    if r.returncode != 0:
        if check:
            raise RuntimeError(f"gh api {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
        return None
    return json.loads(r.stdout) if r.stdout.strip() else None


def cmd_github(repo: str, checks: list[str], dry: bool) -> int:
    info = gh(f"repos/{repo}")
    def do(desc: str, *args: str, data: dict | None = None) -> None:
        print(("would " if dry else "") + desc)
        if not dry:
            gh(*args, data=data)

    do("set merge settings (squash default, delete branch, auto-merge, update branch)",
       "-X", "PATCH", f"repos/{repo}", data={
           "allow_squash_merge": True, "delete_branch_on_merge": True, "allow_auto_merge": True,
           "allow_update_branch": True, "squash_merge_commit_title": "PR_TITLE",
           "squash_merge_commit_message": "PR_BODY"})
    existing = {l["name"] for l in gh(f"repos/{repo}/labels?per_page=100") or []}
    for name, (color, desc) in LABELS.items():
        if name in existing:
            do(f"update label {name}", "-X", "PATCH", f"repos/{repo}/labels/{name}",
               data={"color": color, "description": desc})
        else:
            do(f"create label {name}", "-X", "POST", f"repos/{repo}/labels",
               data={"name": name, "color": color, "description": desc})
    do("Actions: workflow token read-only, approval for all outside contributors' workflows",
       "-X", "PUT", f"repos/{repo}/actions/permissions/workflow",
       data={"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False})
    if not dry:
        # Tighten only GitHub's default; a repository's own choice (looser or stricter) stays.
        cur = gh(f"repos/{repo}/actions/permissions/fork-pr-contributor-approval", check=False) or {}
        if cur.get("approval_policy") in (None, "first_time_contributors"):
            gh("-X", "PUT", f"repos/{repo}/actions/permissions/fork-pr-contributor-approval",
               data={"approval_policy": "all_external_contributors"}, check=False)
        gh("-X", "PUT", f"repos/{repo}/vulnerability-alerts", check=False)
        gh("-X", "PUT", f"repos/{repo}/automated-security-fixes", check=False)
    if info["private"]:
        print("skip rulesets and code scanning: private repository on the Free plan")
        return 0
    do("enable secret scanning with push protection", "-X", "PATCH", f"repos/{repo}", data={
        "security_and_analysis": {"secret_scanning": {"status": "enabled"},
                                  "secret_scanning_push_protection": {"status": "enabled"}}})
    if not dry:
        gh("-X", "PUT", f"repos/{repo}/private-vulnerability-reporting", check=False)
        if gh("-X", "PATCH", f"repos/{repo}/code-scanning/default-setup",
              data={"state": "configured", "query_suite": "extended"}, check=False) is None:
            print("CodeQL default setup not enabled (advanced setup present or unsupported language)")
    rulesets = {r["name"]: r["id"] for r in gh(f"repos/{repo}/rulesets") or []}
    sec = gh(f"repos/{repo}/contents/.github/workflows/security.yml", check=False)
    kit_security = bool(sec) and MANAGED_MARK in __import__("base64").b64decode(sec["content"]).decode()
    contexts = list(dict.fromkeys([*checks, HYGIENE_CHECK, *(SECURITY_CHECKS if kit_security else [])]))
    main_rules = {
        "name": "main", "target": "branch", "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
        "rules": [
            {"type": "deletion"}, {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False, "require_last_push_approval": False,
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["squash", "merge"]}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [{"context": c} for c in contexts]}},
        ],
    }
    if "main" in rulesets:   # keep a stricter existing setup, only add missing checks
        cur = gh(f"repos/{repo}/rulesets/{rulesets['main']}")
        for rule in cur["rules"]:
            if rule["type"] == "required_status_checks":
                have = {c["context"] for c in rule["parameters"]["required_status_checks"]}
                rule["parameters"]["required_status_checks"] += [{"context": c} for c in contexts if c not in have]
        main_rules = {k: cur[k] for k in ("name", "target", "enforcement", "conditions", "bypass_actors", "rules")}
        do(f"update ruleset main (checks: {', '.join(contexts)})", "-X", "PUT",
           f"repos/{repo}/rulesets/{rulesets['main']}", data=main_rules)
    else:
        do(f"create ruleset main (checks: {', '.join(contexts)})", "-X", "POST",
           f"repos/{repo}/rulesets", data=main_rules)
    if "release-tags" not in rulesets:
        do("create ruleset release-tags (v* cannot be moved or deleted)", "-X", "POST",
           f"repos/{repo}/rulesets", data={
               "name": "release-tags", "target": "tag", "enforcement": "active",
               "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
               "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
               "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "update"}]})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("apply", "check"):
        sub.add_parser(name).add_argument("repo", type=Path)
    g = sub.add_parser("github")
    g.add_argument("repo", help="owner/name")
    g.add_argument("--checks", default="", help="required CI check names, comma-separated")
    g.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "apply":
        return cmd_apply(a.repo.resolve())
    if a.cmd == "check":
        return cmd_check(a.repo.resolve())
    return cmd_github(a.repo, [c.strip() for c in a.checks.split(",") if c.strip()], a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
