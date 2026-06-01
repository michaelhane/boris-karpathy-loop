#!/usr/bin/env bash
# review-gate launcher — resolve a Python 3 and run review_gate.py.
#
# Why a launcher: Claude Code hook `command` strings run one fixed program, so
# we cannot "try python3 then python" with `||` (that would re-run the gate when
# the gate itself returned non-zero). A tiny bash shim does the resolution and
# distinguishes "no interpreter" (fail OPEN) from "the gate ran".
#
# Path handling (verified on Windows git-bash): `cd "$(dirname …)"` accepts the
# backslash path Claude passes, and running review_gate.py by RELATIVE name
# sidesteps msys↔Windows path translation (the child inherits this CWD).
#
# Fail-open contract: any inability to run the gate => exit 0; never block work.
set -uo pipefail

payload="$(cat)"

# Cheap pre-filter: only a `git merge`/`git push` can ever trip the gate, so skip
# the Python startup cost on the vast majority of Bash calls that cannot. This is
# a coarse SUPERSET of review_gate.py's own check — it never drops a real
# candidate (a miss here just means the gate stays silent, the safe direction);
# the precise decision is still made in Python.
case "$payload" in
  *git*merge*|*git*push*) : ;;
  *) exit 0 ;;
esac

cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null || exit 0

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1; then
    printf '%s' "$payload" | "$py" review_gate.py
    exit $?
  fi
done

# No Python 3 available — do not block work on a gate that cannot run.
exit 0
