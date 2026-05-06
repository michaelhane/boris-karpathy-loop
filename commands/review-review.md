---
description: Re-evaluate stale review findings against the current code
---

Walk through `reviews/_index.md`, identify findings still marked `status: open`, and check whether they're still valid given the current state of the code.

## Steps

1. Read `reviews/_index.md` to enumerate review files. If it does not exist, exit with: "No review history yet."
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
