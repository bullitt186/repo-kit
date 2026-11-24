"""Tests for scripts/pr_hygiene.py and scripts/kit.py. Run: python3 -m unittest discover tests"""
from __future__ import annotations

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

    def hygiene(self, labels: str = "", association: str = "", body: str | None = None) -> subprocess.CompletedProcess:
        args = [sys.executable, str(HYGIENE), "--base", "main", "--labels", labels,
                "--root", str(self.root), "--author-association", association]
        if body is not None:
            f = self.root.parent / f"{self.root.name}-body.md"
            f.write_text(body, encoding="utf-8")
            args += ["--body-file", str(f)]
        return subprocess.run(args, capture_output=True, text=True)


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


class KitTest(unittest.TestCase):
    def run_kit(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(KITPY), *args], capture_output=True, text=True)

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
        self.assertFalse((r.root / ".github/workflows/pr-hygiene.yml").exists())

    def test_github_origin_gets_reusable_workflow(self) -> None:
        r = Repo()
        git(r.root, "remote", "add", "origin", "https://github.com/o/r.git")
        self.run_kit("apply", str(r.root))
        wf = (r.root / ".github/workflows/pr-hygiene.yml").read_text()
        self.assertIn("hygiene-reusable.yml@stable-v2", wf)
        self.assertFalse((r.root / ".forgejo").exists())

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

    def test_check_reports_drift(self) -> None:
        r = Repo()
        res = self.run_kit("check", str(r.root))
        self.assertEqual(res.returncode, 1)
        self.assertIn("drift  AGENTS.md", res.stdout)


if __name__ == "__main__":
    unittest.main()
