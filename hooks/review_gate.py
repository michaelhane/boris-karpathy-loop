#!/usr/bin/env python3
"""review-gate — a merge/push-to-master review *presence* check.

Part of the boris-karpathy-loop plugin. Runs as a ``PreToolUse`` hook on the
Bash tool. When a git command is about to land code on a *master* branch and it
touches a project-declared "must-review" path that has **no fresh review** in
``reviews/``, the gate surfaces a warning (and, if the project opts in, asks or
blocks). It is a *floor*: it checks **that** a review exists for the diff (by
``commit_hash``), not that the review is good.

Design contract (see COMMIT_PLAN.md Phase J / README "Review gate"):

* **Opt-in per project.** No ``.claude/review-gate.json`` (or ``enabled: false``,
  or an empty ``must_review`` list) => the gate does nothing, silently.
* **Gate the convergence point.** Only ``git merge <ref>`` while on a master
  branch and ``git push ... <master>`` are considered — not per-commit.
* **Warning-first, logged bypass.** Default mode ``warn`` surfaces and proceeds.
  ``ask`` requires confirmation; ``block`` denies. ``REVIEW_GATE_BYPASS=1``
  short-circuits to allow in any mode and is recorded to the gate log.
* **Fail-open, always.** Any error, missing Python feature, non-repo, or
  undeterminable diff => exit 0 and let the work proceed. A broken gate must
  never become a thing people ``--no-verify`` or disable.

Reads the PreToolUse payload (JSON) on stdin; writes a hook decision (JSON) on
stdout. Standard library only — no ``jq``, no third-party deps.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import PurePosixPath

# git global options that consume the following token, so we can find the real
# subcommand in e.g. ``git -C /repo -c k=v push``.
_GIT_OPTS_WITH_ARG = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--exec-path",
}

DEFAULT_MASTER_BRANCHES = ["master", "main"]
DEFAULT_REVIEWS_DIR = "reviews"
DEFAULT_LOG_PATH = ".claude/review-gate-log.jsonl"
DEFAULT_STATE_PATH = ".claude/review-gate-state.json"
DEFAULT_MODE = "warn"
_SHA_RE = re.compile(r"[0-9a-f]{7,40}", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def git(repo: str, *args: str, timeout: int = 10) -> str | None:
    """Run ``git -C repo *args``; return stripped stdout, or None on any failure.

    Encoding is forced to utf-8 with replacement so an exotic filename can never
    crash the gate (the whole point is to fail open, not to fall over).
    """
    try:
        result = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def is_git_repo(repo: str) -> bool:
    return git(repo, "rev-parse", "--is-inside-work-tree") == "true"


def split_segments(command: str) -> list[str]:
    """Split a shell command into top-level segments on && || ; | and newlines."""
    return re.split(r"&&|\|\||;|\n|\|", command)


def parse_git_subcommand(segment: str) -> tuple[str | None, list[str]]:
    """Return (subcommand, args_after_subcommand) for a single ``git`` segment.

    Skips git's pre-subcommand global options. Returns (None, []) if the segment
    is not a git invocation.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    if "git" not in tokens:
        return None, []
    i = tokens.index("git") + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in _GIT_OPTS_WITH_ARG:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok, tokens[i + 1 :]
    return None, []


def positionals(args: list[str]) -> list[str]:
    """Drop option flags (and the value of ``-o``-style short opts we know take
    one) from a subcommand's args, leaving positional operands."""
    out: list[str] = []
    skip = False
    for tok in args:
        if skip:
            skip = False
            continue
        if tok in {"-o", "--repo", "--push-option"}:
            skip = True
            continue
        if tok.startswith("-"):
            continue
        out.append(tok)
    return out


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def load_config(project_dir: str) -> dict | None:
    """Load ``.claude/review-gate.json`` from the project. None if absent/invalid."""
    path = os.path.join(project_dir, ".claude", "review-gate.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _resolve_project_dir(payload: dict) -> str | None:
    """First of cwd / $CLAUDE_PROJECT_DIR / getcwd that git can actually read.

    (A cwd may arrive in a form ``git -C`` cannot open; fall through gracefully.)
    """
    for candidate in (
        payload.get("cwd"),
        os.environ.get("CLAUDE_PROJECT_DIR"),
        os.getcwd(),
    ):
        if candidate and is_git_repo(candidate):
            return candidate
    return None


def _bypassed() -> bool:
    return os.environ.get("REVIEW_GATE_BYPASS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _trigger_enabled(config: dict, name: str, default: bool) -> bool:
    """Read config['triggers'][name], defaulting when the block/key is absent."""
    triggers = config.get("triggers")
    if not isinstance(triggers, dict):
        return default
    return bool(triggers.get(name, default))


def _read_state(project_dir: str) -> dict:
    try:
        with open(
            os.path.join(project_dir, DEFAULT_STATE_PATH), encoding="utf-8"
        ) as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(project_dir: str, state: dict) -> None:
    try:
        path = os.path.join(project_dir, DEFAULT_STATE_PATH)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# op detection
# --------------------------------------------------------------------------- #
def detect_op(command: str, repo: str, master_branches: list[str]) -> dict | None:
    """Detect a master-landing git op in ``command``.

    Returns a descriptor with the ``tip_ref`` (what is being landed), a
    ``diff_range`` for the file list, the target ``branch``, and an optional
    ``needs_ref`` that must exist for the diff to be computable — or None.
    """
    current = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    for segment in split_segments(command):
        sub, args = parse_git_subcommand(segment)
        if sub == "merge":
            op = _detect_merge(args, current, master_branches, repo)
            if op:
                return op
        elif sub == "push":
            op = _detect_push(args, current, master_branches, repo)
            if op:
                return op
    return None


def _detect_merge(
    args: list[str], current: str | None, master_branches: list[str], repo: str
) -> dict | None:
    # A merge only lands on master when you are *on* a master branch.
    if current not in master_branches:
        return None
    refs = positionals(args)
    if not refs:  # e.g. `git merge --continue` / `--abort`
        return None
    # Pick the last positional that actually resolves to a commit. Robust against
    # value-taking flags (`-m <msg>`, `-s <strategy>`, `-X <opt>`, `-F <file>`, …)
    # whose values would otherwise be mistaken for the merged ref.
    ref = None
    for candidate in reversed(refs):
        if git(repo, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"):
            ref = candidate
            break
    if ref is None:
        return None
    # Three-dot: the changes `ref` introduces relative to the merge-base with HEAD.
    return {
        "kind": "merge",
        "tip_ref": ref,
        "diff_range": f"HEAD...{ref}",
        "branch": current,
    }


def _detect_push(
    args: list[str], current: str | None, master_branches: list[str], repo: str
) -> dict | None:
    # `git push [<remote> [<refspec>...]]`: first positional is the remote, the
    # second (if any) is the refspec.
    refs = positionals(args)
    remote = refs[0] if refs else None
    refspec = refs[1] if len(refs) >= 2 else None

    if refspec:
        src, _, dst = refspec.partition(":")
        dst = dst or src  # `master` means `master:master`
        dst_branch = dst.rsplit("/", 1)[-1]  # refs/heads/master -> master
        if dst_branch not in master_branches:
            return None
        tip_ref = src or "HEAD"
    else:
        # Remote-only or bare push: lands on master only if we are on master.
        if current not in master_branches:
            return None
        dst_branch = current
        tip_ref = "HEAD"

    # Resolve the remote so the diff base tracks the *right* ref. Explicit remote
    # wins; else the current branch's upstream remote; else 'origin'.
    if remote is None:
        upstream = git(repo, "rev-parse", "--abbrev-ref", f"{current}@{{upstream}}")
        remote = upstream.split("/", 1)[0] if upstream and "/" in upstream else "origin"
    base = f"{remote}/{dst_branch}"

    return {
        "kind": "push",
        "tip_ref": tip_ref,
        "diff_range": f"{base}..{tip_ref}",
        "branch": dst_branch,
        "needs_ref": base,
    }


# --------------------------------------------------------------------------- #
# scope + presence
# --------------------------------------------------------------------------- #
def _strip_dot_slash(p: str) -> str:
    # Remove a literal leading "./" only — NOT a char-strip (which would mangle
    # dotfiles like ".env" -> "env").
    return p[2:] if p.startswith("./") else p


def path_matches(file: str, pattern: str) -> bool:
    """gitignore-ish match: exact, directory-prefix, fnmatch glob, or pathlib glob."""
    f = _strip_dot_slash(file.replace("\\", "/"))
    p = _strip_dot_slash(pattern.replace("\\", "/"))
    p_dir = p.rstrip("/")
    if f == p_dir:
        return True
    if f.startswith(p_dir + "/"):
        return True
    if fnmatch.fnmatch(f, p):
        return True
    try:
        return PurePosixPath(f).match(p)
    except Exception:
        return False


def must_review_hits(files: list[str], patterns: list[str]) -> list[str]:
    return [f for f in files if any(path_matches(f, pat) for pat in patterns)]


def extract_sha(commit_hash_value: str) -> str | None:
    match = _SHA_RE.search(commit_hash_value)
    return match.group(0).lower() if match else None


def fresh_review_exists(reviews_dir: str, tip_sha: str) -> bool:
    """True if any review file's front-matter ``commit_hash`` SHA matches ``tip_sha``.

    Short/long SHAs match by prefix in either direction (reviews stamp 7-char
    short SHAs; ``tip_sha`` is the full 40).
    """
    if not os.path.isdir(reviews_dir):
        return False
    tip = tip_sha.lower()
    for name in os.listdir(reviews_dir):
        if not name.endswith(".md"):
            continue
        review_sha = _review_commit_sha(os.path.join(reviews_dir, name))
        if review_sha and (tip.startswith(review_sha) or review_sha.startswith(tip)):
            return True
    return False


def _review_commit_sha(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except Exception:
        return None
    # Front-matter is the block between the first two '---' fences.
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    front = text[3:end] if end != -1 else text[3:]
    for line in front.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "commit_hash":
            return extract_sha(value.strip())
    return None


# --------------------------------------------------------------------------- #
# output + logging
# --------------------------------------------------------------------------- #
def log_event(project_dir: str, log_path: str, record: dict) -> None:
    """Append one JSONL line to the gate log. Logging must never block work."""
    try:
        target = (
            log_path if os.path.isabs(log_path) else os.path.join(project_dir, log_path)
        )
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        record = {"ts": datetime.now().isoformat(timespec="seconds"), **record}
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def emit(decision: str | None = None, message: str | None = None) -> None:
    """Print the hook decision JSON (if any). Never uses exit 2 — a structured
    ``deny`` carries the reason and bypass instructions cleanly."""
    out: dict = {}
    if message:
        out["systemMessage"] = message
    if decision:
        out["hookSpecificOutput"] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": message or "",
        }
    if out:
        print(json.dumps(out))


def build_message(op: dict, hits: list[str], tip_sha: str, mode: str) -> str:
    files = ", ".join(hits)
    head = (
        f"⚠️ review-gate: this {op['kind']} to '{op['branch']}' lands changes to "
        f"must-review path(s) [{files}] with NO fresh review in reviews/ for "
        f"{tip_sha[:8]}."
    )
    remedy = (
        "Run /boris-karpathy-loop:review on this diff first (it stamps the review "
        "with this commit), then retry."
    )
    bypass = "To proceed anyway, set REVIEW_GATE_BYPASS=1 (this is logged)."
    if mode == "block":
        return f"{head}\nBLOCKED (mode=block). {remedy}\n{bypass}"
    return f"{head}\n{remedy}\n{bypass}"


# --------------------------------------------------------------------------- #
# decision logic + entry point
# --------------------------------------------------------------------------- #
def evaluate(payload: dict) -> dict | None:
    """Decide what the gate should do for one PreToolUse payload.

    Returns an action ``{"decision": str | None, "message": str}`` to emit, or
    None to stay silent. Pure except for appending to the gate log when the gate
    actually fires or a bypass is honored. Every guard returns None (fail open).
    """
    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or "git" not in command:
        return None
    if "push" not in command and "merge" not in command:
        return None  # hot-path: not a candidate op, skip all git work

    project_dir = _resolve_project_dir(payload)
    if project_dir is None:
        return None

    config = load_config(project_dir)
    if config is None or not config.get("enabled", False):
        return None  # opt-in: no config / disabled -> silent
    if not _trigger_enabled(config, "merge_push", default=True):
        return None  # merge/push trigger turned off for this project
    patterns = config.get("must_review") or []
    if not patterns:
        return None  # nothing declared in scope -> silent

    master_branches = config.get("master_branches") or DEFAULT_MASTER_BRANCHES
    reviews_dir = os.path.join(
        project_dir, config.get("reviews_dir") or DEFAULT_REVIEWS_DIR
    )
    log_path = config.get("log_path") or DEFAULT_LOG_PATH
    mode = config.get("mode") or DEFAULT_MODE

    op = detect_op(command, project_dir, master_branches)
    if op is None:
        return None

    # A required base ref (origin/<master>) must exist to compute the push diff.
    needs_ref = op.get("needs_ref")
    if needs_ref and git(project_dir, "rev-parse", "--verify", needs_ref) is None:
        return None  # cannot determine landing set -> fail open

    tip_sha = git(project_dir, "rev-parse", "--verify", op["tip_ref"])
    if tip_sha is None:
        return None

    diff = git(project_dir, "diff", "--name-only", op["diff_range"])
    if diff is None:
        return None  # diff failed -> fail open
    files = [line.strip() for line in diff.splitlines() if line.strip()]

    hits = must_review_hits(files, patterns)
    if not hits:
        return None  # out of scope -> silent

    if fresh_review_exists(reviews_dir, tip_sha):
        return None  # presence satisfied -> silent

    # ---- the gate fires ----------------------------------------------------- #
    bypassed = _bypassed()
    base_record = {
        "event": "review-gate",
        "op": op["kind"],
        "tip_ref": op["tip_ref"],
        "branch": op["branch"],
        "tip": tip_sha[:8],
        "must_review_hits": hits,
        "fresh_review": False,
        "mode": mode,
    }

    if bypassed:
        log_event(
            project_dir,
            log_path,
            {**base_record, "decision": "allow", "bypassed": True},
        )
        return {
            "decision": None,
            "message": (
                f"review-gate: bypass honored (REVIEW_GATE_BYPASS) for {op['kind']} "
                f"to '{op['branch']}' touching [{', '.join(hits)}] — logged."
            ),
        }

    decision = {"warn": None, "ask": "ask", "block": "deny"}.get(mode)
    log_event(
        project_dir,
        log_path,
        {**base_record, "decision": decision or "warn", "bypassed": False},
    )
    return {"decision": decision, "message": build_message(op, hits, tip_sha, mode)}


def _stop_diff_files(
    project_dir: str, master_branches: list[str], head: str
) -> list[str] | None:
    """Files in HEAD's commits vs the master line (merge-base diff).

    Falls back to unpushed commits (``origin/<master>``) when on master itself.
    Returns [] when nothing is ahead of master, or None if the diff failed.
    """
    base = None
    for mb in master_branches:
        cand = git(project_dir, "merge-base", "HEAD", mb)
        if cand and cand != head:
            base = cand
            break
    if base is None:
        for mb in master_branches:
            ref = f"origin/{mb}"
            if git(project_dir, "rev-parse", "--verify", ref) is None:
                continue
            cand = git(project_dir, "merge-base", "HEAD", ref)
            if cand and cand != head:
                base = cand
                break  # stop at the first *usable* base, not the first that exists
    if base is None:
        return []  # on master with nothing ahead, or no master line -> nothing to nudge
    diff = git(project_dir, "diff", "--name-only", f"{base}..HEAD")
    if diff is None:
        return None
    return [line.strip() for line in diff.splitlines() if line.strip()]


def evaluate_stop(payload: dict) -> dict | None:
    """Stop-hook nudge. Returns a soft ``{"decision": None, "message": ...}`` when
    HEAD carries committed-but-unreviewed must-review changes, else None (silent /
    fail open). Debounced once per HEAD via ``.claude/review-gate-state.json``."""
    project_dir = _resolve_project_dir(payload)
    if project_dir is None:
        return None

    config = load_config(project_dir)
    if config is None or not config.get("enabled", False):
        return None
    if not _trigger_enabled(config, "stop_nudge", default=False):
        return None  # opt-in: the Stop nudge is off by default
    patterns = config.get("must_review") or []
    if not patterns:
        return None

    head = git(project_dir, "rev-parse", "--verify", "HEAD")
    if head is None:
        return None

    # Debounce: evaluate each HEAD at most once (backs up the launcher's check).
    # Record the HEAD *before* deciding to nudge, on purpose: even a head that
    # turns out out-of-scope or unreviewable must not be re-evaluated every turn.
    # Trade-off: a transient git failure on this head won't be retried — acceptable
    # for a soft nudge (the merge gate is the hard backstop).
    state = _read_state(project_dir)
    if state.get("last_evaluated_head") == head:
        return None
    state["last_evaluated_head"] = head
    _write_state(project_dir, state)

    master_branches = config.get("master_branches") or DEFAULT_MASTER_BRANCHES
    files = _stop_diff_files(project_dir, master_branches, head)
    if not files:
        return None  # nothing ahead of master / diff failed -> silent

    hits = must_review_hits(files, patterns)
    if not hits:
        return None  # out of scope -> silent

    reviews_dir = os.path.join(
        project_dir, config.get("reviews_dir") or DEFAULT_REVIEWS_DIR
    )
    if fresh_review_exists(reviews_dir, head):
        return None  # already reviewed -> silent

    if _bypassed():
        return None  # bypass silences the soft nudge

    log_path = config.get("log_path") or DEFAULT_LOG_PATH
    log_event(
        project_dir,
        log_path,
        {
            "event": "review-gate-nudge",
            "op": "stop",
            "tip": head[:8],
            "must_review_hits": hits,
            "fresh_review": False,
            "decision": "nudge",
        },
    )
    files_str = ", ".join(hits)
    message = (
        f"⚠️ review-gate: HEAD ({head[:8]}) has unreviewed changes to must-review "
        f"path(s) [{files_str}]. Run /boris-karpathy-loop:review before you merge or "
        f"wrap up — this clears once a review stamps this commit (shown once per commit)."
    )
    return {"decision": None, "message": message}


def main() -> None:
    stop_mode = "--stop" in sys.argv[1:]
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return  # unparseable payload -> fail open
    if not isinstance(payload, dict):
        return
    action = evaluate_stop(payload) if stop_mode else evaluate(payload)
    if action is not None:
        emit(action.get("decision"), action.get("message"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # absolute backstop: never let an unexpected error block the user
    sys.exit(0)
