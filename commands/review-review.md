---
description: Re-evaluate stale review findings against the current code
---

Walk through the review files in `reviews/` — read each one's front-matter `status:` — identify findings still marked `status: open`, and check whether they're still valid given the current state of the code.

## Steps

1. Enumerate review files directly: glob `reviews/*.md` (exclude `_index.md` and `_metrics.md`) and read each one's front-matter `status:`. **Per-review front-matter is the source of truth; `_index.md` is a derived view (regenerated in step 5), never the gate for which files you examine.** If there are no review files, exit with: "No review history yet."
2. For each review file with `status: open` in its frontmatter:
   a. Read the file.
   b. Compare its `commit_hash` to the current `git rev-parse HEAD`.
   c. For each finding, re-read the referenced file at the cited line and decide:
      - **resolved** — the issue is no longer present
      - **still-valid** — the issue still exists at or near the cited location
      - **stale** — the file changed substantially; the original line/issue can no longer be located
      - **cannot-verify** — needs human judgment
3. Update each review's frontmatter:
   - `status: closed` if all findings are resolved
   - `status: stale` if commit_hash is old AND the file changed substantially
   - `status: open` otherwise
4. Append a `## Re-review {YYYY-MM-DD}` section to the review's body documenting the resolution status of each finding.
5. Regenerate `reviews/_index.md` with up-to-date status counts.

## Bias

Do not auto-resolve. If unsure, leave the finding open and flag for human review. The cost of a false-resolved is higher than the cost of a lingering finding.

## Suggested cadence

Run `/review-review` weekly, or before a release, or whenever `reviews/` starts feeling like a graveyard.

## Closing the loop

The review-status lifecycle has three layers, in order of preference:

1. **Same-commit (happy path).** When you ship a fix for a finding, flip that review's front-matter `status:` and its `_index.md` line *in the same commit as the fix*. The review and the code never diverge.
2. **`/loop-bootstrap` (detection).** At session start it treats per-review front-matter `status:` as the source of truth and flags any `status: open` review whose `commit_hash` is far behind HEAD — a likely *false-open* (fix shipped, status never flipped).
3. **`/review-review` (catch-up net).** This command — re-evaluate and write back when detection flags drift or the cadence comes due.

Layer 1 is discipline, not mechanism — and discipline alone failed once: the `v0.2-setup-and-diagnose` review read `open` for 23 days after commit `130b720` had already fixed every finding. Layers 2–3 exist because of that. If reconciling reviews by hand ever gets error-prone at scale, that is the trigger to build a small `scripts/close_finding.py` (flip front-matter `status:` + `_index.md` line atomically, fail-loud, idempotent) — not before; YAGNI at single-digit review counts.
