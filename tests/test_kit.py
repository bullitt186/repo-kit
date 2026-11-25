"""Tests for scripts/pr_hygiene.py and scripts/kit.py. Run: python3 -m unittest discover tests"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
HYGIENE = KIT / "scripts" / "pr_hygiene.py"
KITPY = KIT / "scripts" / "kit.py"

GOOD_ADR = """# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

c

## Decision

d

## Consequences

e
"""
# kit.py resolves the stable commit from GitHub; tests stay offline with a fixed one (ADR-0011).
PINNED = "1" * 40
os.environ["REPO_KIT_SHA"] = PINNED
INDEX = "| [0001](0001-record-architecture-decisions.md) | Record | Accepted |\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


class Repo:
    """Temporary git repository with a base commit on main and a feature branch."""

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        self.write({"README.md": "# r\n", "src/app.py": "x = 1\n", **(files or {})})
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        git(self.root, "checkout", "-qb", "feature")

    def write(self, files: dict[str, str]) -> None:
        for rel, content in files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    def commit(self, files: dict[str, str]) -> None:
        self.write(files)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "change")

    def hygiene(self, labels: str = "", association: str = "", body: str | None = None,
                today: str = "2027-01-01") -> subprocess.CompletedProcess:
        args = [sys.executable, str(HYGIENE), "--base", "main", "--labels", labels,
                "--root", str(self.root), "--author-association", association, "--today", today]
        if body is not None:
            f = self.root.parent / f"{self.root.name}-body.md"
            f.write_text(body, encoding="utf-8")
            args += ["--body-file", str(f)]
        return subprocess.run(args, capture_output=True, text=True, check=False)


class HygieneTest(unittest.TestCase):
    def test_code_without_test_fails_and_label_waives(self) -> None:
        r = Repo()
        r.commit({"src/app.py": "x = 2\n"})
        res = r.hygiene()
        self.assertEqual(res.returncode, 1)
        self.assertIn("code changed without a test change", res.stdout)
        self.assertEqual(r.hygiene("no-test-change").returncode, 0)

    def test_code_with_test_passes(self) -> None:
        r = Repo()
        r.commit({"src/app.py": "x = 2\n", "tests/test_app.py": "assert True\n"})
        self.assertEqual(r.hygiene().returncode, 0, r.hygiene().stdout)

    def test_docs_only_change_needs_nothing(self) -> None:
        r = Repo({"CHANGELOG.md": "# Changelog\n"})
        r.commit({"README.md": "# r\n\nmore\n", "docs/x.md": "y\n"})
        self.assertEqual(r.hygiene().returncode, 0)

    def test_changelog_required_when_present(self) -> None:
        r = Repo({"CHANGELOG.md": "# Changelog\n"})
        r.commit({"src/app.py": "x = 2\n", "tests/test_app.py": "t\n"})
        res = r.hygiene()
        self.assertEqual(res.returncode, 1)
        self.assertIn("CHANGELOG.md", res.stdout)
        self.assertEqual(r.hygiene("skip-changelog").returncode, 0)
        r.commit({"CHANGELOG.md": "# Changelog\n\n- fix\n"})
        self.assertEqual(r.hygiene().returncode, 0)

    def test_changelog_none_in_config(self) -> None:
        r = Repo({"CHANGELOG.md": "# C\n", ".github/repo-kit.yml": "changelog: none\n"})
        r.commit({"src/app.py": "x = 2\n", "tests/test_app.py": "t\n"})
        self.assertEqual(r.hygiene().returncode, 0)

    def test_custom_test_paths(self) -> None:
        r = Repo({".github/repo-kit.yml": "test_paths:\n  - spec/**\n"})
        r.commit({"src/app.py": "x = 2\n", "tests/test_app.py": "t\n"})
        self.assertEqual(r.hygiene().returncode, 1)   # tests/ is not a test path here
        r.commit({"spec/app_check.rb": "t\n"})
        self.assertEqual(r.hygiene().returncode, 0)

    def test_deleting_code_needs_no_test(self) -> None:
        r = Repo({"src/old.py": "y\n"})
        git(r.root, "rm", "-q", "src/old.py")
        git(r.root, "commit", "-qm", "rm")
        self.assertEqual(r.hygiene().returncode, 0)

    def test_valid_adr_passes(self) -> None:
        r = Repo()
        r.commit({"docs/adr/README.md": INDEX, "docs/adr/0001-record-architecture-decisions.md": GOOD_ADR})
        self.assertEqual(r.hygiene().returncode, 0, r.hygiene().stdout)

    def test_adr_errors(self) -> None:
        cases = {
            "missing section": GOOD_ADR.replace("## Consequences\n", ""),
            "bad status": GOOD_ADR.replace("Accepted", "Maybe"),
            "bad date": GOOD_ADR.replace("2026-11-24", "24.11.2026"),
            "wrong title": GOOD_ADR.replace("# ADR-0001:", "# ADR-0002:"),
        }
        for why, text in cases.items():
            with self.subTest(why):
                r = Repo()
                r.commit({"docs/adr/README.md": INDEX, "docs/adr/0001-record-architecture-decisions.md": text})
                self.assertEqual(r.hygiene().returncode, 1, why)

    def test_adr_superseded_status_is_valid(self) -> None:
        r = Repo()
        r.commit({"docs/adr/README.md": INDEX, "docs/adr/0001-record-architecture-decisions.md":
                  GOOD_ADR.replace("Accepted", "Superseded by ADR-0002")})
        self.assertEqual(r.hygiene().returncode, 0, r.hygiene().stdout)

    def test_adr_not_in_index_and_duplicate_number(self) -> None:
        r = Repo()
        r.commit({"docs/adr/README.md": INDEX, "docs/adr/0001-record-architecture-decisions.md": GOOD_ADR,
                  "docs/adr/0001-other.md": GOOD_ADR})
        out = r.hygiene().stdout
        self.assertIn("also used by", out)
        self.assertIn("0001-other.md: not listed", out)

    def test_adr_bad_filename(self) -> None:
        r = Repo()
        r.commit({"docs/adr/README.md": INDEX, "docs/adr/0001-record-architecture-decisions.md": GOOD_ADR,
                  "docs/adr/My Decision.md": GOOD_ADR})
        self.assertIn("name must be", r.hygiene().stdout)

    def test_broken_link_in_changed_markdown(self) -> None:
        r = Repo({"docs/a.md": "a\n"})
        r.commit({"README.md": "[ok](docs/a.md) [web](https://x.invalid) [anchor](#a) [bad](docs/missing.md)\n"
                              "```\n[code](not/a/link.md)\n```\n"})
        res = r.hygiene()
        self.assertEqual(res.returncode, 1)
        self.assertIn("docs/missing.md", res.stdout)
        self.assertNotIn("not/a/link.md", res.stdout)
        self.assertNotIn("docs/a.md'", res.stdout)


class DependencyUpdateTest(unittest.TestCase):
    def test_labelled_dependency_update_needs_no_test_or_changelog(self) -> None:
        r = Repo({"CHANGELOG.md": "# C\n", "package.json": "{}\n"})
        r.commit({"package.json": '{"a": "2"}\n', "package-lock.json": "{}\n"})
        self.assertEqual(r.hygiene().returncode, 1)                  # without the label it is code
        self.assertEqual(r.hygiene("dependencies").returncode, 0)

    def test_renovate_config_is_not_code(self) -> None:
        r = Repo({"CHANGELOG.md": "# C\n"})
        r.commit({"renovate.json": "{}\n"})
        self.assertEqual(r.hygiene().returncode, 0, r.hygiene().stdout)

    def test_label_does_not_cover_code(self) -> None:
        r = Repo({"package.json": "{}\n"})
        r.commit({"package.json": '{"a": "2"}\n', "src/app.py": "x = 3\n"})
        self.assertEqual(r.hygiene("dependencies").returncode, 1)


class ScopeRulesTest(unittest.TestCase):
    def test_scope_change_needs_adr(self) -> None:
        r = Repo({"docs/SCOPE.md": "# Scope\n", "docs/adr/README.md": INDEX,
                  "docs/adr/0001-record-architecture-decisions.md": GOOD_ADR})
        r.commit({"docs/SCOPE.md": "# Scope\n\nnew direction\n"})
        self.assertIn("docs/SCOPE.md changed without an ADR", r.hygiene().stdout)
        r.commit({"docs/adr/0002-new-direction.md": GOOD_ADR.replace("0001", "0002"),
                  "docs/adr/README.md": INDEX + "| [0002](0002-new-direction.md) | x | Accepted |\n"})
        self.assertEqual(r.hygiene().returncode, 0, r.hygiene().stdout)

    def test_outside_contributor_needs_issue_reference(self) -> None:
        r = Repo()
        r.commit({"src/app.py": "x = 2\n", "tests/test_app.py": "t\n"})
        for assoc in ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "NONE"):
            with self.subTest(assoc):
                res = r.hygiene(association=assoc, body="Adds a thing")
                self.assertEqual(res.returncode, 1)
                self.assertIn("linked issue", res.stdout)
                self.assertEqual(r.hygiene(association=assoc, body="Closes #12").returncode, 0)
        self.assertEqual(r.hygiene(association="OWNER", body="no issue").returncode, 0)
        self.assertEqual(r.hygiene(association="", body="no issue").returncode, 0)   # Forgejo: no association

    def test_outside_docs_change_needs_no_issue(self) -> None:
        r = Repo()
        r.commit({"README.md": "# r\n\ntypo fixed\n"})
        self.assertEqual(r.hygiene(association="FIRST_TIME_CONTRIBUTOR", body="typo").returncode, 0)

    def test_size_limit_and_lockfiles(self) -> None:
        r = Repo({".github/repo-kit.yml": "max_lines: 10\n"})
        r.commit({"src/big.py": "x\n" * 11, "tests/test_big.py": "t\n"})
        res = r.hygiene()
        self.assertEqual(res.returncode, 1)
        self.assertIn("exceed 10", res.stdout)
        self.assertEqual(r.hygiene("large-change").returncode, 0)
        r2 = Repo({".github/repo-kit.yml": "max_lines: 10\n"})
        r2.commit({"package-lock.json": "{}\n" * 50, "src/a.py": "x = 3\n", "tests/test_a.py": "t\n"})
        self.assertEqual(r2.hygiene().returncode, 0, r2.hygiene().stdout)
        r3 = Repo({".github/repo-kit.yml": "max_lines: 10\n"})
        r3.commit({"docs/guide.md": "line\n" * 50})   # docs do not count
        self.assertEqual(r3.hygiene().returncode, 0, r3.hygiene().stdout)


class GracePeriodTest(unittest.TestCase):
    def test_new_rule_warns_before_its_date_and_blocks_after(self) -> None:
        r = Repo({".github/repo-kit.yml": "max_lines: 10\n"})
        r.commit({"src/big.py": "x\n" * 11, "tests/test_big.py": "t\n"})
        before = r.hygiene(today="2026-12-14")
        self.assertEqual(before.returncode, 0)
        self.assertIn("blocks from 2026-12-15", before.stdout)
        self.assertEqual(r.hygiene(today="2026-12-15").returncode, 1)

    def test_rules_without_date_block_immediately(self) -> None:
        r = Repo()
        r.commit({"src/app.py": "x = 2\n"})
        self.assertEqual(r.hygiene(today="2000-01-01").returncode, 1)


class GithubSlugTest(unittest.TestCase):
    def test_exact_host_only(self) -> None:
        sys.path.insert(0, str(KIT / "scripts"))
        import kit  # noqa: PLC0415
        self.assertEqual(kit.github_slug("https://github.com/o/r.git"), "o/r")
        self.assertEqual(kit.github_slug("git@github.com:o/r.git"), "o/r")
        self.assertEqual(kit.github_slug("ssh://git@github.com/o/r"), "o/r")
        self.assertIsNone(kit.github_slug("https://github.com.evil.example/o/r.git"))
        self.assertIsNone(kit.github_slug("https://evil.example/github.com/o/r.git"))
        self.assertIsNone(kit.github_slug("ssh://git@forge.example.invalid:2222/o/r.git"))


class CodeqlDetectionTest(unittest.TestCase):
    def test_advanced_codeql_workflow_is_detected(self) -> None:
        import base64  # noqa: PLC0415
        sys.path.insert(0, str(KIT / "scripts"))
        import kit  # noqa: PLC0415
        files = {"repos/o/r/contents/.github/workflows": [{"name": "ci.yml", "path": ".github/workflows/ci.yml"},
                                                          {"name": "sec.yml", "path": ".github/workflows/sec.yml"}],
                 "repos/o/r/contents/.github/workflows/ci.yml": {"content": base64.b64encode(b"run: pytest").decode()},
                 "repos/o/r/contents/.github/workflows/sec.yml":
                     {"content": base64.b64encode(b"uses: github/codeql-action/init@x").decode()}}
        original = kit.gh
        try:
            kit.gh = lambda path, **_: files.get(path)
            self.assertTrue(kit.has_codeql_workflow("o/r"))
            del files["repos/o/r/contents/.github/workflows/sec.yml"]
            files["repos/o/r/contents/.github/workflows"].pop()
            self.assertFalse(kit.has_codeql_workflow("o/r"))
        finally:
            kit.gh = original


class ForgejoConfigTest(unittest.TestCase):
    def fake(self, protections: list, fork: bool = False):
        calls = []
        def call(method, path, data=None):
            calls.append((method, path, data))
            if method == "GET" and path == "/repos/o/r":
                return {"default_branch": "main", "fork": fork, "original_url": ""}
            if method == "GET" and path.startswith("/repos/o/r/labels"):
                return [{"name": "bug", "id": 7}]
            if method == "GET" and path == "/repos/o/r/branch_protections":
                return protections
            return None
        return call, calls

    def kit(self):
        sys.path.insert(0, str(KIT / "scripts"))
        import kit  # noqa: PLC0415
        return kit

    def test_labels_and_new_protection(self) -> None:
        kit = self.kit()
        call, calls = self.fake([])
        self.assertEqual(kit.cmd_forgejo("o/r", "api", ["ci / test (pull_request)"], False, call=call), 0)
        self.assertIn(("PATCH", "/repos/o/r/labels/7"), [(m, p) for m, p, _ in calls])
        created = {d["name"] for m, p, d in calls if m == "POST" and p == "/repos/o/r/labels"}
        self.assertIn("accepted", created)
        self.assertNotIn("bug", created)
        post = next(d for m, p, d in calls if m == "POST" and p == "/repos/o/r/branch_protections")
        self.assertEqual(post["rule_name"], "main")
        self.assertTrue(post["enable_push"])
        self.assertEqual(post["status_check_contexts"], ["ci / test (pull_request)", *kit.FORGEJO_CHECKS])

    def test_existing_protection_keeps_its_checks(self) -> None:
        kit = self.kit()
        call, calls = self.fake([{"rule_name": "main", "status_check_contexts": ["Old / x (pull_request)"]}])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            kit.cmd_forgejo("o/r", "api", [], False, call=call)
        self.assertIn("warning: keeping existing required check 'Old / x (pull_request)'", out.getvalue())
        patch = next(d for m, p, d in calls if m == "PATCH" and p == "/repos/o/r/branch_protections/main")
        self.assertEqual(patch["status_check_contexts"], ["Old / x (pull_request)", *kit.FORGEJO_CHECKS])

    def test_dry_run_writes_nothing_and_forks_are_refused(self) -> None:
        kit = self.kit()
        call, calls = self.fake([])
        kit.cmd_forgejo("o/r", "api", [], True, call=call)
        self.assertEqual({m for m, _, _ in calls}, {"GET"})
        call, calls = self.fake([], fork=True)
        self.assertEqual(kit.cmd_forgejo("o/r", "api", [], False, call=call), 2)


class UpdateTest(unittest.TestCase):
    """kit.py update against a local bare repository as origin (no network)."""

    def setUp(self) -> None:
        self.r = Repo()
        git(self.r.root, "checkout", "-q", "main")
        self.bare = Path(tempfile.mkdtemp()) / "origin.git"
        git(self.r.root.parent, "init", "-q", "--bare", "-b", "main", str(self.bare))
        git(self.r.root, "remote", "add", "origin", str(self.bare))
        git(self.r.root, "push", "-q", "-u", "origin", "main")
        git(self.r.root, "remote", "set-head", "origin", "main")

    def update(self) -> dict:
        res = subprocess.run([sys.executable, str(KITPY), "update", "--no-push", str(self.r.root)],
                             capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout.strip().splitlines()[-1])

    def test_repo_without_kit_is_reported_not_changed(self) -> None:
        out = self.update()
        self.assertIn("no kit yet", out["status"])
        self.assertIn("percent", out)
        self.assertFalse((self.r.root / ".claude/worktrees/kit-update").exists())

    def test_outdated_kit_repo_gets_an_update_commit_and_clean_checkout_stays(self) -> None:
        self.r.write({"AGENTS.md": "# A\n\n<!-- repo-kit:begin v1 -->\nold\n<!-- repo-kit:end -->\n"})
        git(self.r.root, "add", "-A")
        git(self.r.root, "commit", "-qm", "kit v1")
        git(self.r.root, "push", "-q", "origin", "main")
        out = self.update()
        self.assertTrue(out["status"].startswith("update:"), out)
        branch = [b for b in git(self.r.root, "branch").split() if b.startswith("chore/repo-kit-update-")]
        self.assertEqual(len(branch), 1)
        self.assertIn("repo-kit:begin v", git(self.r.root, "show", f"{branch[0]}:AGENTS.md"))
        self.assertEqual(git(self.r.root, "status", "--porcelain"), "")   # the checkout itself is untouched

    def test_scorecard_table_and_drop(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        prev = tmp / "prev.md"
        prev.write_text("| Repo | Gesamt |\n|---|---|\n| a | 80 % |\n| b | 50 % |\n", encoding="utf-8")
        lines = "\n".join([json.dumps({"repo": "a", "percent": 70, "score": {"tests": "green", "lint": "red"}}),
                           json.dumps({"repo": "b", "percent": 60, "score": {"tests": "green", "lint": "green"}}),
                           json.dumps({"repo": "c", "status": "fork, skipped"})])
        res = subprocess.run([sys.executable, str(KITPY), "scorecard", "--out", str(tmp / "out.md"),
                              "--previous", str(prev)], input=lines, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, res.stderr)
        table = (tmp / "out.md").read_text(encoding="utf-8")
        self.assertIn("| a | 70 % | -10 | 🟢 | 🔴 |", table)
        self.assertIn("| b | 60 % | +10 | 🟢 | 🟢 |", table)
        self.assertIn("fork, skipped", table)
        self.assertEqual(res.stdout.strip(), "drop a: 80 % → 70 %")


class KitTest(unittest.TestCase):
    def run_kit(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(KITPY), *args], capture_output=True, text=True, check=False)

    def test_apply_on_empty_repo_creates_setup_and_is_idempotent(self) -> None:
        r = Repo()
        self.assertEqual(self.run_kit("apply", str(r.root)).returncode, 0)
        for rel in ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "CHANGELOG.md",
                    ".github/pull_request_template.md", ".github/workflows/pr-hygiene.yml",
                    "docs/adr/README.md", "docs/adr/template.md",
                    "docs/adr/0001-record-architecture-decisions.md"):
            self.assertTrue((r.root / rel).exists(), rel)
        self.assertNotIn("{{DATE}}", (r.root / "docs/adr/0001-record-architecture-decisions.md").read_text())
        self.assertEqual(self.run_kit("apply", str(r.root)).stdout, "")   # nothing left to write
        res = self.run_kit("check", str(r.root))
        self.assertEqual(res.returncode, 1)   # seeded AGENTS.md still has TODOs
        self.assertIn("TODO", res.stdout)

    def test_seeded_adr_passes_hygiene(self) -> None:
        r = Repo()
        self.run_kit("apply", str(r.root))
        git(r.root, "add", "-A")
        git(r.root, "commit", "-qm", "kit")
        self.assertEqual(r.hygiene().returncode, 0, r.hygiene().stdout)

    def test_existing_files_keep_their_own_text(self) -> None:
        r = Repo({"AGENTS.md": "# Repo rules\n\nOwn text.\n", "CONTRIBUTING.md": "# Contributing\n\nOwn.\n",
                  "CLAUDE.md": "Claude only.\n", "docs/adr/0007-x.md": "keep\n"})
        self.run_kit("apply", str(r.root))
        agents = (r.root / "AGENTS.md").read_text()
        self.assertTrue(agents.startswith("# Repo rules\n\n<!-- repo-kit:begin"))
        self.assertIn("Own text.", agents)
        self.assertIn("Own.", (r.root / "CONTRIBUTING.md").read_text())
        self.assertTrue((r.root / "CLAUDE.md").read_text().startswith("@AGENTS.md\n\nClaude only."))
        self.assertFalse((r.root / "docs/adr/0001-record-architecture-decisions.md").exists())
        self.assertEqual((r.root / "docs/adr/0007-x.md").read_text(), "keep\n")

    def test_empty_adr_folder_still_gets_adr_0001(self) -> None:
        r = Repo()
        (r.root / "docs" / "adr").mkdir(parents=True)
        self.run_kit("apply", str(r.root))
        self.assertTrue((r.root / "docs/adr/0001-record-architecture-decisions.md").exists())

    def test_block_is_refreshed_not_duplicated(self) -> None:
        r = Repo({"AGENTS.md": "# A\n\n<!-- repo-kit:begin v0 -->\nold\n<!-- repo-kit:end -->\n\nmine\n"})
        self.run_kit("apply", str(r.root))
        text = (r.root / "AGENTS.md").read_text()
        self.assertEqual(text.count("<!-- repo-kit:begin"), 1)
        self.assertNotIn("\nold\n", text)
        self.assertIn("mine", text)

    def test_forgejo_origin_gets_forgejo_workflow(self) -> None:
        r = Repo()
        git(r.root, "remote", "add", "origin", "ssh://git@forge.example.invalid:2222/o/r.git")
        self.run_kit("apply", str(r.root))
        self.assertTrue((r.root / ".forgejo/workflows/pr-hygiene.yml").exists())
        self.assertIn('"minimumReleaseAge": "7 days"', (r.root / "renovate.json").read_text())
        self.assertFalse((r.root / ".github/dependabot.yml").exists())
        self.assertFalse((r.root / ".github/workflows/pr-hygiene.yml").exists())

    def test_github_origin_gets_reusable_workflow(self) -> None:
        r = Repo()
        git(r.root, "remote", "add", "origin", "https://github.com/o/r.git")
        self.run_kit("apply", str(r.root))
        wf = (r.root / ".github/workflows/pr-hygiene.yml").read_text()
        self.assertIn(f"hygiene-reusable.yml@{PINNED} # stable-v2\n", wf)
        self.assertIn(f"security-reusable.yml@{PINNED} # stable-v2\n",
                      (r.root / ".github/workflows/security.yml").read_text())
        self.assertNotIn("{{", wf)
        self.assertFalse((r.root / ".forgejo").exists())

    def test_pin_moves_on_apply_and_any_pin_is_in_sync_for_check(self) -> None:
        r = Repo()
        git(r.root, "remote", "add", "origin", "https://github.com/o/r.git")
        self.run_kit("apply", str(r.root))
        wf = r.root / ".github/workflows/pr-hygiene.yml"
        older = wf.read_text().replace(PINNED, "2" * 40)
        wf.write_text(older)
        self.assertNotIn("drift  .github/workflows/pr-hygiene.yml", self.run_kit("check", str(r.root)).stdout)
        wf.write_text(older.replace(f"@{'2' * 40} # stable-v2", "@stable-v2"))   # unpinned, as before ADR-0011
        self.assertIn("drift  .github/workflows/pr-hygiene.yml", self.run_kit("check", str(r.root)).stdout)
        wf.write_text(older)
        self.assertEqual(self.run_kit("apply", str(r.root)).stdout, "wrote .github/workflows/pr-hygiene.yml\n")
        self.assertIn(f"@{PINNED} # stable-v2\n", wf.read_text())

    def test_malformed_pin_override_is_refused(self) -> None:
        r = Repo()
        git(r.root, "remote", "add", "origin", "https://github.com/o/r.git")
        res = subprocess.run([sys.executable, str(KITPY), "apply", str(r.root)], capture_output=True, text=True,
                             check=False, env={**os.environ, "REPO_KIT_SHA": "stable-v2"})
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("40-character", res.stderr)
        self.assertFalse((r.root / ".github/workflows/pr-hygiene.yml").exists())

    def test_forgejo_workflow_change_is_not_code(self) -> None:
        r = Repo()
        r.commit({".forgejo/workflows/x.yml": "on: push\n"})
        self.assertEqual(r.hygiene().returncode, 0)

    def test_v1_pr_template_is_upgraded_custom_one_is_kept(self) -> None:
        r = Repo({".github/pull_request_template.md": "<!-- Definition of Done: CONTRIBUTING.md. Tick only what you did; old -->\n"})
        self.run_kit("apply", str(r.root))
        self.assertIn("Managed by repo-kit", (r.root / ".github/pull_request_template.md").read_text())
        r2 = Repo({".github/pull_request_template.md": "Our own template\n"})
        self.run_kit("apply", str(r2.root))
        self.assertEqual((r2.root / ".github/pull_request_template.md").read_text(), "Our own template\n")
        self.assertIn("custom .github/pull_request_template.md", self.run_kit("check", str(r2.root)).stdout)

    def test_apply_refuses_forks_unless_own_product(self) -> None:
        r = Repo()
        git(r.root, "remote", "add", "upstream", "https://forge.example.invalid/other/project.git")
        res = self.run_kit("apply", str(r.root))
        self.assertEqual(res.returncode, 2)
        self.assertIn("fork", res.stdout)
        self.assertFalse((r.root / "AGENTS.md").exists())
        self.assertEqual(self.run_kit("apply", "--own-product", str(r.root)).returncode, 0)
        self.assertTrue((r.root / "AGENTS.md").exists())

    def test_score_lights(self) -> None:
        r = Repo()
        res = json.loads(self.run_kit("score", "--json", str(r.root)).stdout)
        self.assertEqual(res["disciplines"]["instructions"]["light"], "red")
        self.assertEqual(res["percent"], 0)
        self.run_kit("apply", str(r.root))
        r.write({".github/repo-kit.yml": "ci_exceptions:\n  - \"types: no type checker for this language\"\n",
                 ".github/workflows/ci.yml": "steps:\n  - run: pytest && ruff check . && mutmut run\n"})
        res = json.loads(self.run_kit("score", "--json", str(r.root)).stdout)
        d = {k: v["light"] for k, v in res["disciplines"].items()}
        self.assertEqual(d["instructions"], "yellow")   # seeded AGENTS.md still has TODOs
        self.assertEqual(d["scope"], "yellow")
        self.assertEqual((d["adrs"], d["hygiene"], d["security"]), ("green", "green", "green"))
        self.assertEqual((d["tests"], d["lint"], d["mutation"]), ("green", "green", "green"))
        self.assertEqual(d["types"], "n/a")
        self.assertEqual(d["stop hook"], "yellow")      # FAST_CHECK still TODO
        self.assertTrue(0 < res["percent"] < 100)

    def test_check_reports_drift(self) -> None:
        r = Repo()
        res = self.run_kit("check", str(r.root))
        self.assertEqual(res.returncode, 1)
        self.assertIn("drift  AGENTS.md", res.stdout)


if __name__ == "__main__":
    unittest.main()
