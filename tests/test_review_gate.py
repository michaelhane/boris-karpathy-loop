#!/usr/bin/env python3
"""Acceptance + unit tests for hooks/review_gate.py.

Each test spins up a throwaway git repo (and, for the push case, a bare origin),
writes a real .claude/review-gate.json, and drives review_gate.py as a
subprocess with a synthetic PreToolUse payload on stdin — exercising the real
git/diff/front-matter path, not mocks.

Stdlib only. Run:  python -m unittest tests.test_review_gate -v
                or: python tests/test_review_gate.py
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
GATE = str(HOOKS_DIR / "review_gate.py")

IN_SCOPE = "src/triage_ledger.py"
OUT_OF_SCOPE = "docs/notes.md"
MUST_REVIEW = ["src/triage_ledger.py", "scripts/sync_*.py", "src/matching/**"]


def _force_rm(func, path, _exc):
    # Windows: git pack files are read-only; clear the bit and retry.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def git(repo: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo, *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write(repo: str, rel: str, content: str) -> None:
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ReviewGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="review-gate-test-")
        self.addCleanup(self._cleanup)
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "commit.gpgsign", "false")
        # Baseline commit on a branch we force to 'master' (version-independent).
        write(self.repo, "README.md", "init\n")
        write(self.repo, IN_SCOPE, "v0\n")
        write(self.repo, OUT_OF_SCOPE, "v0\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "init")
        git(self.repo, "branch", "-M", "master")

    def _cleanup(self) -> None:
        import shutil

        shutil.rmtree(self.repo, onerror=_force_rm)

    # -- helpers ---------------------------------------------------------- #
    def make_feature(self, branch: str, changes: dict[str, str]) -> str:
        git(self.repo, "checkout", "-q", "-b", branch)
        for rel, content in changes.items():
            write(self.repo, rel, content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", f"work on {branch}")
        tip = git(self.repo, "rev-parse", branch)
        git(self.repo, "checkout", "-q", "master")
        return tip

    def write_config(self, **over) -> None:
        cfg = {
            "enabled": True,
            "mode": "ask",
            "must_review": MUST_REVIEW,
            "master_branches": ["master", "main"],
            "reviews_dir": "reviews",
            "log_path": ".claude/review-gate-log.jsonl",
        }
        cfg.update(over)
        write(self.repo, ".claude/review-gate.json", json.dumps(cfg))

    def write_review(self, sha: str, name: str = "rev.md") -> None:
        front = f"---\ndate: 2026-06-01\ncommit_hash: {sha[:7]}\nstatus: closed\n---\n\n# Review\n"
        write(self.repo, f"reviews/{name}", front)

    def run_gate(
        self, command: str, env_extra: dict | None = None
    ) -> tuple[dict | None, int]:
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": self.repo,
        }
        env = os.environ.copy()
        env.pop("REVIEW_GATE_BYPASS", None)
        if env_extra:
            env.update(env_extra)
        result = subprocess.run(
            [sys.executable, GATE],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        out = result.stdout.strip()
        obj = json.loads(out) if out else None
        return obj, result.returncode

    def log_lines(self) -> list[dict]:
        path = Path(self.repo) / ".claude" / "review-gate-log.jsonl"
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def run_stop(self, env_extra: dict | None = None) -> tuple[dict | None, int]:
        payload = {"hook_event_name": "Stop", "cwd": self.repo}
        env = os.environ.copy()
        env.pop("REVIEW_GATE_BYPASS", None)
        if env_extra:
            env.update(env_extra)
        result = subprocess.run(
            [sys.executable, GATE, "--stop"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        out = result.stdout.strip()
        obj = json.loads(out) if out else None
        return obj, result.returncode

    # -- acceptance cases ------------------------------------------------- #
    def test_merge_in_scope_no_review_fires_ask(self) -> None:
        """ACCEPTANCE: merge-to-master of a must-review path without a fresh
        review -> warning (mode=ask here) + a logged event."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1 money logic\n"})
        self.write_config(mode="ask")
        obj, code = self.run_gate("git merge feature/ledger")
        self.assertEqual(code, 0)
        self.assertIsNotNone(obj, "gate should have fired")
        assert obj is not None  # narrow for the type checker
        self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("systemMessage", obj)
        self.assertIn(IN_SCOPE, obj["systemMessage"])
        lines = self.log_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["op"], "merge")
        self.assertFalse(lines[0]["bypassed"])
        self.assertIn(IN_SCOPE, lines[0]["must_review_hits"])

    def test_merge_out_of_scope_is_silent(self) -> None:
        """ACCEPTANCE: paths outside the declared scope -> completely silent."""
        self.make_feature("feature/docs", {OUT_OF_SCOPE: "new notes\n"})
        self.write_config(mode="ask")
        obj, code = self.run_gate("git merge feature/docs")
        self.assertEqual(code, 0)
        self.assertIsNone(obj, "out-of-scope merge must be silent")
        self.assertEqual(self.log_lines(), [])

    def test_merge_in_scope_with_fresh_review_is_silent(self) -> None:
        """In-scope but a review stamps the merged tip -> presence satisfied."""
        tip = self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(mode="ask")
        self.write_review(tip)
        obj, code = self.run_gate("git merge feature/ledger")
        self.assertEqual(code, 0)
        self.assertIsNone(obj, "a fresh review for the tip must satisfy the gate")

    def test_no_config_is_silent(self) -> None:
        """Opt-in: with no .claude/review-gate.json the gate does nothing."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        obj, code = self.run_gate("git merge feature/ledger")
        self.assertEqual(code, 0)
        self.assertIsNone(obj)

    def test_disabled_config_is_silent(self) -> None:
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(enabled=False)
        obj, _ = self.run_gate("git merge feature/ledger")
        self.assertIsNone(obj)

    def test_bypass_env_allows_and_logs(self) -> None:
        """REVIEW_GATE_BYPASS=1 -> allowed, but recorded as a bypass."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(mode="block")
        obj, code = self.run_gate(
            "git merge feature/ledger", {"REVIEW_GATE_BYPASS": "1"}
        )
        self.assertEqual(code, 0)
        self.assertIsNotNone(obj)
        assert obj is not None
        self.assertNotIn("hookSpecificOutput", obj)  # no deny/ask -> proceeds
        self.assertIn("bypass", obj["systemMessage"].lower())
        lines = self.log_lines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0]["bypassed"])
        self.assertEqual(lines[0]["decision"], "allow")

    def test_warn_mode_surfaces_without_blocking(self) -> None:
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(mode="warn")
        obj, _ = self.run_gate("git merge feature/ledger")
        self.assertIsNotNone(obj)
        assert obj is not None
        self.assertNotIn("hookSpecificOutput", obj)  # warn -> no permissionDecision
        self.assertIn("systemMessage", obj)

    def test_block_mode_denies(self) -> None:
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(mode="block")
        obj, _ = self.run_gate("git merge feature/ledger")
        self.assertIsNotNone(obj)
        assert obj is not None
        self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_merge_when_not_on_master_is_silent(self) -> None:
        """Merging while NOT on a master branch is not a master-landing op."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        git(self.repo, "checkout", "-q", "-b", "integration")
        self.write_config(mode="ask")
        obj, _ = self.run_gate("git merge feature/ledger")
        self.assertIsNone(obj)

    def test_non_git_command_is_silent(self) -> None:
        self.write_config(mode="ask")
        obj, code = self.run_gate("echo merge push to master")
        self.assertEqual(code, 0)
        self.assertIsNone(obj)

    def test_chained_command_detects_push(self) -> None:
        """A push buried in an && chain is still detected (against a real origin)."""
        bare = tempfile.mkdtemp(prefix="review-gate-origin-")
        self.addCleanup(lambda: __import__("shutil").rmtree(bare, onerror=_force_rm))
        git(bare, "init", "--bare")
        git(self.repo, "remote", "add", "origin", bare.replace("\\", "/"))
        git(self.repo, "push", "-q", "origin", "master")
        # New in-scope commit on master, not yet pushed.
        write(self.repo, IN_SCOPE, "v1 money\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "ledger change")
        self.write_config(mode="ask")
        obj, code = self.run_gate("git add -A && git push origin master")
        self.assertEqual(code, 0)
        self.assertIsNotNone(obj, "push to master with in-scope change should fire")
        assert obj is not None
        self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(self.log_lines()[0]["op"], "push")

    # -- regressions for the v0.3.0 self-review concerns ------------------ #
    def test_merge_with_message_flag_fires(self) -> None:
        """CONCERN regression: `git merge -m <msg> <ref>` — the message value
        must not be mistaken for the merged ref."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1 money\n"})
        self.write_config(mode="ask")
        obj, _ = self.run_gate('git merge -m "ship the ledger" feature/ledger')
        self.assertIsNotNone(obj, "merge with -m should still fire")
        assert obj is not None
        self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(self.log_lines()[0]["tip_ref"], "feature/ledger")

    def test_push_to_non_origin_remote_fires(self) -> None:
        """CONCERN regression: a push to a non-`origin` remote must use that
        remote's tracking ref for the diff base (no hardcoded origin/)."""
        bare = tempfile.mkdtemp(prefix="review-gate-upstream-")
        self.addCleanup(lambda: __import__("shutil").rmtree(bare, onerror=_force_rm))
        git(bare, "init", "--bare")
        git(self.repo, "remote", "add", "upstream", bare.replace("\\", "/"))
        git(self.repo, "push", "-q", "upstream", "master")
        write(self.repo, IN_SCOPE, "v1 money\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "ledger change")
        self.write_config(mode="ask")
        obj, _ = self.run_gate("git push upstream master")
        self.assertIsNotNone(obj, "push to a non-origin remote should fire")
        assert obj is not None
        self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(self.log_lines()[0]["op"], "push")

    def test_dotfile_not_overmatched(self) -> None:
        """NIT regression: '.env' must not be mangled to 'env' and over-match."""
        self.make_feature("feature/env", {".env": "SECRET=1\n"})
        self.write_config(must_review=["env"])  # pattern 'env', landing file '.env'
        obj, _ = self.run_gate("git merge feature/env")
        self.assertIsNone(obj, ".env must not match an 'env' scope")

    def test_messy_commit_hash_in_review_satisfies(self) -> None:
        """Presence-check tolerates real-world `commit_hash` annotations."""
        tip = self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(mode="ask")
        front = (
            f"---\ncommit_hash: {tip[:7]} (uncommitted, base HEAD)\nstatus: open\n---\n"
        )
        write(self.repo, "reviews/messy.md", front)
        obj, _ = self.run_gate("git merge feature/ledger")
        self.assertIsNone(obj, "messy commit_hash should still match the tip")

    # -- v0.3.1 stop-nudge cases ----------------------------------------- #
    def test_stop_nudge_fires_on_committed_unreviewed(self) -> None:
        """ACCEPTANCE: committed must-review change on a branch, no review -> a soft
        (non-blocking) systemMessage nudge."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1 money\n"})
        git(self.repo, "checkout", "-q", "feature/ledger")
        self.write_config(triggers={"stop_nudge": True})
        obj, code = self.run_stop()
        self.assertEqual(code, 0)
        self.assertIsNotNone(obj, "stop nudge should fire")
        assert obj is not None
        self.assertIn("systemMessage", obj)
        self.assertNotIn("hookSpecificOutput", obj)  # soft -> never blocks
        self.assertIn(IN_SCOPE, obj["systemMessage"])
        self.assertEqual(self.log_lines()[0]["op"], "stop")

    def test_stop_nudge_silent_when_reviewed(self) -> None:
        tip = self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        git(self.repo, "checkout", "-q", "feature/ledger")
        self.write_config(triggers={"stop_nudge": True})
        self.write_review(tip)
        obj, _ = self.run_stop()
        self.assertIsNone(obj, "a review stamping HEAD must silence the nudge")

    def test_stop_nudge_silent_out_of_scope(self) -> None:
        self.make_feature("feature/docs", {OUT_OF_SCOPE: "notes\n"})
        git(self.repo, "checkout", "-q", "feature/docs")
        self.write_config(triggers={"stop_nudge": True})
        obj, _ = self.run_stop()
        self.assertIsNone(obj)

    def test_stop_nudge_silent_when_trigger_off(self) -> None:
        """Opt-in: stop_nudge defaults False when triggers is absent."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        git(self.repo, "checkout", "-q", "feature/ledger")
        self.write_config()
        obj, _ = self.run_stop()
        self.assertIsNone(obj)

    def test_stop_nudge_debounced_per_head(self) -> None:
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        git(self.repo, "checkout", "-q", "feature/ledger")
        self.write_config(triggers={"stop_nudge": True})
        first, _ = self.run_stop()
        self.assertIsNotNone(first, "first stop should nudge")
        second, _ = self.run_stop()
        self.assertIsNone(second, "second stop on the same HEAD should be debounced")

    def test_merge_gate_off_when_trigger_disabled(self) -> None:
        """triggers.merge_push=false disables the merge gate (backward-compat: absent=on)."""
        self.make_feature("feature/ledger", {IN_SCOPE: "v1\n"})
        self.write_config(mode="ask", triggers={"merge_push": False})
        obj, _ = self.run_gate("git merge feature/ledger")
        self.assertIsNone(obj, "merge gate should be off when merge_push=false")

    def test_stop_nudge_fallback_uses_usable_remote_base(self) -> None:
        """CONCERN regression: on master, a stale origin/master at HEAD must not
        shadow a usable origin/main in the fallback base resolution."""
        bare = tempfile.mkdtemp(prefix="review-gate-fb-")
        self.addCleanup(lambda: __import__("shutil").rmtree(bare, onerror=_force_rm))
        git(bare, "init", "--bare")
        git(self.repo, "remote", "add", "origin", bare.replace("\\", "/"))
        base_sha = git(self.repo, "rev-parse", "HEAD")  # the init commit
        # origin/main lags at the init commit (a usable base); no local main exists.
        git(self.repo, "push", "-q", "origin", f"{base_sha}:refs/heads/main")
        # New in-scope commit on master, then origin/master pushed to HEAD so its
        # merge-base with HEAD == HEAD (stale-at-head -> must be skipped, not break).
        write(self.repo, IN_SCOPE, "v1 money\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "ledger on master")
        git(self.repo, "push", "-q", "origin", "master")
        self.write_config(triggers={"stop_nudge": True})
        obj, _ = self.run_stop()
        self.assertIsNotNone(
            obj, "fallback must use origin/main when origin/master is stale-at-head"
        )
        assert obj is not None
        self.assertIn(IN_SCOPE, obj["systemMessage"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
