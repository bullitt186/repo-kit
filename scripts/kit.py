#!/usr/bin/env python3
"""repo-kit: one consistent contributor and agent setup for every repository.

  kit.py apply  <repo-dir>             add missing files, refresh managed blocks
  kit.py check  <repo-dir>             report drift from the kit (exit 1 on drift)
  kit.py score  <repo-dir> [--json]    traffic light per discipline of the standard (ADR-0009)
  kit.py update <repo-dir> [--no-push] score origin's default branch, apply the kit in a throwaway
                                       worktree, push a dated update branch and open a pull request
  kit.py scorecard --out F [--previous F]  turn `update` JSON lines on stdin into a Markdown table
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
import re
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


GITHUB_URL = re.compile(r"^(?:https://|ssh://git@|git@)github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$")


def github_slug(url: str) -> str | None:
    """owner/name when the URL points to github.com (exact host), else None."""
    m = GITHUB_URL.match(url.strip())
    return m.group(1) if m else None


def forge(repo: Path) -> str:
    """'github' when origin is on github.com or there is no origin, else 'forgejo'."""
    r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo, capture_output=True, text=True, check=False)
    return "github" if r.returncode != 0 or github_slug(r.stdout) else "forgejo"


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


# Discipline -> words that show it in CI workflows, Makefile or package scripts (ADR-0009).
CI_SIGNS = {
    "tests": ("pytest", "unittest", "vitest", "jest", "go test", "cargo test", "make test",
              "npm test", "pnpm test", "run_tests", "ctest", "swift test", "playwright"),
    "lint": ("ruff", "eslint", "oxlint", "golangci", "gofmt", "clang-format", "clang-tidy",
             "shellcheck", "yamllint", "pylint", "flake8", "prettier", "markdownlint",
             "stylelint", "hadolint", "biome", "swift-format", "actionlint"),
    "types": ("mypy", "tsc", "pyright", "go vet", "typecheck", "type-check"),
    "mutation": ("mutmut", "stryker", "mull", "gremlins", "mutate"),
}


def is_fork(repo: Path) -> bool:
    """A fork of someone else's project: GitHub reports it, or the clone has an upstream remote."""
    remotes = subprocess.run(["git", "remote"], cwd=repo, capture_output=True, text=True, check=False).stdout.split()
    if "upstream" in remotes:
        return True
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo,
                         capture_output=True, text=True, check=False).stdout.strip()
    slug = github_slug(url)
    if slug:
        info = gh(f"repos/{slug}", check=False)
        return bool(info and info.get("fork"))
    return False


def score(repo: Path) -> dict[str, tuple[str, str]]:
    """Discipline -> (light, note). Lights: green, yellow, red, n/a."""
    def text(rel: str) -> str:
        f = repo / rel
        return f.read_text(encoding="utf-8") if f.exists() else ""

    out: dict[str, tuple[str, str]] = {}
    drift = {str(p.relative_to(repo)) for p in planned(repo)}
    agents = text("AGENTS.md")
    if "repo-kit:begin" not in agents:
        out["instructions"] = ("red", "no repo-kit block")
    elif {"AGENTS.md", "CONTRIBUTING.md"} & drift or "TODO" in agents:
        out["instructions"] = ("yellow", f"block older than v{VERSION} or TODOs left")
    else:
        out["instructions"] = ("green", "")
    scope = text("docs/SCOPE.md")
    out["scope"] = ("red", "missing") if not scope else ("yellow", "TODOs left") if "TODO" in scope else ("green", "")
    adrs = list((repo / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    out["adrs"] = ("green", f"{len(adrs)}") if adrs and text("docs/adr/README.md") else ("red", "no ADRs")
    flows = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for d in (".github/workflows", ".forgejo/workflows")
                      for f in sorted((repo / d).glob("*.y*ml")))
    hygiene = next(p for p in managed_files(repo) if p.name == "pr-hygiene.yml")
    if not hygiene.exists():
        out["hygiene"] = ("red", "no PR hygiene workflow")
    else:
        out["hygiene"] = ("yellow", "older kit version") if str(hygiene.relative_to(repo)) in drift else ("green", "")
    out["security"] = ("green", "") if "gitleaks" in flows or "security-reusable.yml" in flows else ("red", "no secret scan in CI")
    upd = any((repo / f).exists() for f in (".github/dependabot.yml", "renovate.json", "renovate.json5",
                                             ".renovaterc", ".github/renovate.json"))
    out["updates"] = ("green", "") if upd else ("red", "no Dependabot or Renovate")
    stop = text("scripts/agent-stop-check.sh")
    if "agent-stop-check" not in text(".claude/settings.json"):
        out["stop hook"] = ("red", "not registered")
    else:
        out["stop hook"] = ("yellow", "fast check TODO") if 'FAST_CHECK="TODO"' in stop else ("green", "")
    signs = (flows + text("Makefile") + text("package.json") + text("pyproject.toml")).lower()
    exceptions = {e.split(":")[0].strip(): e for e in load_list(repo, "ci_exceptions")}
    for disc, words in CI_SIGNS.items():
        if disc in exceptions:
            out[disc] = ("n/a", exceptions[disc].split(":", 1)[-1].strip())
        else:
            found = any(w in signs for w in words)
            out[disc] = ("green", "") if found else ("red", "not found in CI or build files")
    return out


def load_list(repo: Path, key: str) -> list[str]:
    """List values of `key` in .github/repo-kit.yml (same minimal format as pr_hygiene.py)."""
    f = repo / ".github" / "repo-kit.yml"
    items, current = [], None
    for raw in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
        line = raw.split(" #")[0].rstrip()
        if line.lstrip().startswith("- ") and current == key:
            items.append(line.lstrip()[2:].strip().strip("\"'"))
        elif ":" in line and not line.startswith(" "):
            current = line.split(":", 1)[0].strip()
    return items


def cmd_score(repo: Path, as_json: bool) -> int:
    result = score(repo)
    points = [{"green": 1.0, "yellow": 0.5, "red": 0.0}[light] for light, _ in result.values() if light != "n/a"]
    pct = round(100 * sum(points) / len(points)) if points else 100
    if as_json:
        print(json.dumps({"repo": repo.name, "percent": pct, "kit": VERSION,
                          "disciplines": {k: {"light": light, "note": n} for k, (light, n) in result.items()}}))
    else:
        for k, (light, n) in result.items():
            print(f"{light:6} {k}" + (f"  ({n})" if n else ""))
        print(f"{pct} %")
    return 0


def git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def cmd_update(repo: Path, push: bool) -> int:
    """Weekly pull of the kit into one repository (ADR-0009). Prints one JSON line."""
    result: dict = {"repo": repo.name, "forge": forge(repo)}
    if is_fork(repo):
        result["status"] = "fork, skipped"
        print(json.dumps(result))
        return 0
    git_out(repo, "fetch", "-q", "origin")
    default = git_out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")
    wt = repo / ".claude" / "worktrees" / "kit-update"
    if wt.exists():
        git_out(repo, "worktree", "remove", "--force", str(wt))
    branch = f"chore/repo-kit-update-{dt.date.today():%Y%m%d}"
    git_out(repo, "worktree", "add", "-q", "-B", branch, str(wt), f"origin/{default}")
    try:
        before = score(wt)
        result["score"] = {k: light for k, (light, _) in before.items()}
        points = [{"green": 1.0, "yellow": 0.5, "red": 0.0}[v] for v in result["score"].values() if v != "n/a"]
        result["percent"] = round(100 * sum(points) / len(points)) if points else 100
        agents = wt / "AGENTS.md"
        if not agents.exists() or "repo-kit:begin" not in agents.read_text(encoding="utf-8"):
            result["status"] = "no kit yet (adopt per SOP new-repo)"
            return 0
        changed = planned(wt)
        if not changed:
            result["status"] = "up to date"
            return 0
        cmd_apply(wt)
        git_out(wt, "add", "-A")
        git_out(wt, "commit", "-q", "-m", f"chore: repo-kit update (v{VERSION})\n\nFiles refreshed by kit.py update.")
        todo = findings(wt)
        result["status"] = f"update: {len(changed)} file(s)" + (f", {len(todo)} finding(s) for an agent" if todo else "")
        result["findings"] = todo
        if push:
            git_out(wt, "push", "-q", "-u", "origin", branch)
            result["branch"] = branch
            if result["forge"] == "github":
                body = ("Files refreshed by `kit.py update` (repo-kit v" + VERSION + ").\n\n"
                        + ("Findings that need a person or agent:\n" + "\n".join(f"- {f}" for f in todo)
                           if todo else "No findings; merges when CI is green."))
                url = subprocess.run(["gh", "pr", "create", "--base", default, "--head", branch, "--title",
                                      f"chore: repo-kit update (v{VERSION})", "--body", body],
                                     cwd=wt, capture_output=True, text=True, check=False).stdout.strip()
                result["pr"] = url
                if url and not todo:
                    subprocess.run(["gh", "pr", "merge", url, "--auto", "--squash"], cwd=wt,
                                   capture_output=True, text=True, check=False)
        return 0
    finally:
        print(json.dumps(result))
        git_out(repo, "worktree", "remove", "--force", str(wt))


def cmd_scorecard(out: Path, previous: Path | None) -> int:
    """Markdown table of `update` JSON lines from stdin, with the trend against a previous table."""
    rows = [json.loads(line) for line in sys.stdin if line.strip().startswith("{")]
    old: dict[str, int] = {}
    if previous and previous.exists():
        for line in previous.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[1].endswith("%") and cells[1][:-2].strip().isdigit():
                old[cells[0]] = int(cells[1][:-2])
    icon = {"green": "🟢", "yellow": "🟡", "red": "🔴", "n/a": "⚪"}
    disciplines = list(next((r["score"] for r in rows if "score" in r), {}).keys())
    lines = ["| Repo | Gesamt | Trend | " + " | ".join(disciplines) + " | Status |",
             "|---|---|---|" + "---|" * len(disciplines) + "---|"]
    drops = []
    for r in sorted(rows, key=lambda r: r.get("percent", -1)):
        if "score" not in r:
            lines.append(f"| {r['repo']} | - | - |" + " - |" * len(disciplines) + f" {r.get('status', '')} |")
            continue
        prev = old.get(r["repo"])
        trend = "neu" if prev is None else f"{r['percent'] - prev:+d}"
        if prev is not None and r["percent"] < prev:
            drops.append(f"{r['repo']}: {prev} % → {r['percent']} %")
        lines.append(f"| {r['repo']} | {r['percent']} % | {trend} | "
                     + " | ".join(icon[r["score"].get(d, "n/a")] for d in disciplines) + f" | {r.get('status', '')} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for d in drops:
        print(f"drop {d}")
    return 0


def cmd_apply(repo: Path, own_product: bool = False) -> int:
    if is_fork(repo) and not own_product:
        print("refusing: this is a fork of someone else's project; their rules apply (ADR-0010). "
              "Keep your own notes in an untracked CLAUDE.local.md, or pass --own-product after "
              "recording in an ADR that the fork became your own product.")
        return 2
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
                       capture_output=True, text=True, check=False)
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
    existing = {lab["name"] for lab in gh(f"repos/{repo}/labels?per_page=100") or []}
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
    a_p = sub.add_parser("apply")
    a_p.add_argument("repo", type=Path)
    a_p.add_argument("--own-product", action="store_true", help="apply to a fork that became your own product")
    sub.add_parser("check").add_argument("repo", type=Path)
    u_p = sub.add_parser("update")
    u_p.add_argument("repo", type=Path)
    u_p.add_argument("--no-push", action="store_true")
    c_p = sub.add_parser("scorecard")
    c_p.add_argument("--out", type=Path, required=True)
    c_p.add_argument("--previous", type=Path)
    s_p = sub.add_parser("score")
    s_p.add_argument("repo", type=Path)
    s_p.add_argument("--json", action="store_true")
    g = sub.add_parser("github")
    g.add_argument("repo", help="owner/name")
    g.add_argument("--checks", default="", help="required CI check names, comma-separated")
    g.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "apply":
        return cmd_apply(a.repo.resolve(), a.own_product)
    if a.cmd == "update":
        return cmd_update(a.repo.resolve(), not a.no_push)
    if a.cmd == "scorecard":
        return cmd_scorecard(a.out, a.previous)
    if a.cmd == "score":
        return cmd_score(a.repo.resolve(), a.json)
    if a.cmd == "check":
        return cmd_check(a.repo.resolve())
    return cmd_github(a.repo, [c.strip() for c in a.checks.split(",") if c.strip()], a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
