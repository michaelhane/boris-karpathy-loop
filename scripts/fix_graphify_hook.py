#!/usr/bin/env python3
"""
fix_graphify_hook.py — make the graphify post-commit hook reliable on Windows.

The hook installed by `graphify hook install` detects its Python interpreter by
reading the shebang of the `graphify` launcher. On Windows / Git-Bash that
launcher is a PE binary (`graphify.exe`) and `command -v graphify` often reports
it *without* the extension, so the hook:

  1. runs `head -1` on the binary, whose NUL bytes make bash warn
     "command substitution: ignored null byte in input"; and
  2. falls back to a system `python`/`python3` that cannot import the
     uv-isolated graphify, so the background rebuild silently no-ops and
     `GRAPH_REPORT.md` drifts from HEAD until someone runs `graphify update .`
     by hand.

This script patches the installed hook to short-circuit that path on Windows:
when the launcher is a `.exe`, it drives the `graphify` CLI directly
(`graphify update .`, AST-only, no API), which uses its own venv interpreter.
The patch is a no-op on macOS/Linux, where graphify is a normal script the
existing shebang detection reads fine.

`.git/hooks/` is not version-controlled and is overwritten by `graphify hook
install`, so this script is the durable, re-runnable record of the fix: run it
again after any reinstall.

Idempotent: a second run reports "already patched" and changes nothing.
Fails loudly: if the hook is missing, not graphify-installed, or its shape has
drifted so the anchor can't be found, it explains and exits non-zero rather
than writing a broken hook.

Usage:
    python scripts/fix_graphify_hook.py            # patch .git/hooks/post-commit
    python scripts/fix_graphify_hook.py --dry-run  # show the diff, write nothing
    python scripts/fix_graphify_hook.py --hook path/to/post-commit
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Present in every hook written by `graphify hook install`.
GRAPHIFY_MARKER = "graphify-hook-start"
# Our own marker — drives idempotency.
FIX_MARKER = "boris-karpathy-loop v0.2.3 nullbyte-fix"
# The launcher-detection line we insert our short-circuit after. Stable across
# graphify versions: it is the core of the hook.
ANCHOR_RE = re.compile(
    r"^[ \t]*GRAPHIFY_BIN=\$\(command -v graphify\b[^\n]*$", re.MULTILINE
)

PATCH_BLOCK = """
# >>> boris-karpathy-loop v0.2.3 nullbyte-fix >>>
# Windows/Git-Bash: the graphify launcher is a PE binary (graphify.exe) and
# `command -v` may report it without the extension. The interpreter detection
# below then runs `head -1` on the binary (bash warns "ignored null byte in
# input") and falls back to a system python that cannot import the uv-isolated
# graphify, so the rebuild silently no-ops and the graph drifts from HEAD.
# Drive the graphify CLI directly instead (AST-only, no API). The rebase/merge
# skip and the changed-files check above have already run; the CLI launcher
# resolves its own venv interpreter. No-op on macOS/Linux, where graphify is a
# script the block below reads fine.
case "$GRAPHIFY_BIN" in
    *.exe) _BKL_GRAPHIFY_EXE="$GRAPHIFY_BIN" ;;
    ?*)    _BKL_GRAPHIFY_EXE=""; [ -e "${GRAPHIFY_BIN}.exe" ] && _BKL_GRAPHIFY_EXE="${GRAPHIFY_BIN}.exe" ;;
    *)     _BKL_GRAPHIFY_EXE="" ;;
esac
if [ -n "$_BKL_GRAPHIFY_EXE" ]; then
    _BKL_LOG="${HOME}/.cache/graphify-rebuild.log"
    mkdir -p "$(dirname "$_BKL_LOG")"
    echo "[graphify hook] launching background rebuild via CLI (log: $_BKL_LOG)"
    nohup "$_BKL_GRAPHIFY_EXE" update . > "$_BKL_LOG" 2>&1 < /dev/null &
    disown 2>/dev/null || true
    exit 0
fi
# <<< boris-karpathy-loop v0.2.3 nullbyte-fix <<<"""


def resolve_hook_path(explicit: str | None) -> Path:
    """Return the post-commit hook path, from --hook or `git rev-parse`."""
    if explicit:
        return Path(explicit)
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(f"error: not a git repository (or git unavailable): {exc}")
    return Path(git_dir) / "hooks" / "post-commit"


def patch_text(text: str) -> tuple[str, str]:
    """Return (new_text, status). status in: patched, already, not-graphify, no-anchor."""
    if FIX_MARKER in text:
        return text, "already"
    if GRAPHIFY_MARKER not in text:
        return text, "not-graphify"
    match = ANCHOR_RE.search(text)
    if not match:
        return text, "no-anchor"
    new_text = text[: match.end()] + PATCH_BLOCK + text[match.end() :]
    return new_text, "patched"


def write_atomic(path: Path, new_text: str) -> None:
    """Write new_text to path atomically, preserving mode and LF line endings."""
    mode = path.stat().st_mode
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".post-commit.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Make the graphify post-commit hook reliable on Windows."
    )
    parser.add_argument(
        "--hook",
        help="path to the post-commit hook (default: <git-dir>/hooks/post-commit)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the diff without writing"
    )
    args = parser.parse_args()

    hook = resolve_hook_path(args.hook)
    if not hook.is_file():
        sys.exit(
            f"error: hook not found: {hook}\n  (run `graphify hook install` first)"
        )

    text = hook.read_text(encoding="utf-8")
    new_text, status = patch_text(text)

    if status == "not-graphify":
        sys.exit(
            f"error: {hook} is not a graphify-installed hook (no '{GRAPHIFY_MARKER}' marker)."
        )
    if status == "no-anchor":
        sys.exit(
            f"error: could not locate the `GRAPHIFY_BIN=$(command -v graphify ...)` line in {hook}.\n"
            "  The graphify hook shape has changed - review it by hand before patching."
        )
    if status == "already":
        print(f"Already patched - '{FIX_MARKER}' present in {hook}. Nothing to do.")
        return 0

    if args.dry_run:
        diff = difflib.unified_diff(
            text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"{hook} (current)",
            tofile=f"{hook} (patched)",
        )
        sys.stdout.writelines(diff)
        print(f"\n[dry-run] would patch {hook} (no changes written).")
        return 0

    write_atomic(hook, new_text)
    print(f"Patched {hook}")
    print("  Windows post-commit now drives `graphify update .` via the CLI launcher.")
    print(
        "  Re-run this script after any `graphify hook install` (it overwrites the hook)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
