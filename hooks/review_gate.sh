#!/usr/bin/env bash
# review-gate launcher — resolve a Python 3 and run review_gate.py.
#
# Two modes:
#   (no arg)  PreToolUse merge/push gate — pre-filtered on the command in stdin.
#   --stop    Stop-hook review nudge — pre-checked cheaply so Python only starts
#             for an opted-in project on a NEW HEAD (Stop fires every turn).
#
# Why a launcher: a hook `command` runs one fixed program, so we cannot "try
# python3 then python" with `||`. A shim resolves the interpreter and tells "no
# interpreter" (fail OPEN) apart from "the gate ran".
#
# Path handling (verified on Windows git-bash): cd to the script dir and run
# review_gate.py by RELATIVE name to sidestep msys<->Windows path translation;
# normalize $CLAUDE_PROJECT_DIR with `cygpath -m` so both `git -C` and `test -f`
# accept it (no-op off Windows).
#
# Fail-open contract: any inability to run the gate => exit 0; never block work.
set -uo pipefail

mode="${1:-}"
payload="$(cat)"

if [ "$mode" = "--stop" ]; then
  # Cheap, Python-free pre-checks — this path fires on EVERY turn once installed.
  proj="${CLAUDE_PROJECT_DIR:-}"
  [ -n "$proj" ] || exit 0
  if command -v cygpath >/dev/null 2>&1; then
    proj="$(cygpath -m "$proj" 2>/dev/null || printf '%s' "$proj")"
  fi
  cfg="$proj/.claude/review-gate.json"
  [ -f "$cfg" ] || exit 0
  grep -Eq '"stop_nudge"[[:space:]]*:[[:space:]]*true' "$cfg" 2>/dev/null || exit 0
  head="$(git -C "$proj" rev-parse HEAD 2>/dev/null)" || exit 0
  [ -n "$head" ] || exit 0
  state="$proj/.claude/review-gate-state.json"
  if [ -f "$state" ] && grep -Eq "\"last_evaluated_head\"[[:space:]]*:[[:space:]]*\"$head\"" "$state" 2>/dev/null; then
    exit 0  # already evaluated this HEAD -> no Python spawn
  fi
else
  # Merge/push gate: only a git merge/push can trip it — skip Python otherwise.
  case "$payload" in
    *git*merge* | *git*push*) : ;;
    *) exit 0 ;;
  esac
fi

cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null || exit 0

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1; then
    if [ "$mode" = "--stop" ]; then
      printf '%s' "$payload" | "$py" review_gate.py --stop
    else
      printf '%s' "$payload" | "$py" review_gate.py
    fi
    exit $?
  fi
done

# No Python 3 available — do not block work on a gate that cannot run.
exit 0
