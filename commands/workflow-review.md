---
description: Heavy multi-agent Karpathy review panel — planner shards the diff, reviewers fan out, every blocker/concern is adversarially verified, one canonical review lands in reviews/
---

Run the **planner-driven review panel** for the current repository. This is the
heavy counterpart to `/review` — use it for large or risky changes, not typos.

## Steps

1. **Scope the diff.** Run:
   ```bash
   git rev-parse HEAD
   git status --short
   git diff HEAD --numstat
   ```
   - If `$ARGUMENTS` names a commit range (e.g. `HEAD~3..HEAD`) or a file set, scope to that instead.
   - If there are no uncommitted changes and no range was given, ask the user whether to scope to a range or stop. Do **not** launch the panel on an empty diff.

2. **Read the gate config (optional).** If `.claude/review-gate.json` exists, read its `must_review` array and pass it as risk hints. If absent, pass `[]`.

3. **Capture the date.** Run `date +%F`. The Workflow script cannot compute the date itself, so it must be passed in.

4. **Launch the panel.** Call the `Workflow` tool with:
   - `scriptPath`: `${CLAUDE_PLUGIN_ROOT}/workflows/workflow-review.js`
   - `args` (a JSON object):
     ```json
     {
       "today": "<output of date +%F>",
       "commitHash": "<output of git rev-parse HEAD>",
       "range": "<HEAD~3..HEAD, or null for uncommitted>",
       "scopeFiles": ["<path>", "..."],
       "mustReview": ["<glob>", "..."],
       "reviewsDir": "reviews",
       "principlesPath": "${CLAUDE_PLUGIN_ROOT}/agents/karpathy-reviewer.md"
     }
     ```
     Use `null` for `range` when reviewing uncommitted changes, and `null` for `scopeFiles` when reviewing every changed file.
   This command's instruction to call `Workflow` is the explicit opt-in the tool requires.

5. **Report.** When the workflow finishes, print the `summary` it returns — nothing more. Do not list every finding inline; the `reviews/` artifact is the source of truth.

6. **Do NOT auto-fix.** The panel reports only. The user decides what to act on.

## If the Workflow tool is unavailable

Some environments don't expose the `Workflow` tool. If you cannot call it, say so
plainly and offer to run `/review` (the single-agent path) instead. Do **not**
silently fall back, and do not try to re-implement the panel by hand.

## Notes

- Heavy by design: the panel spawns a planner, one reviewer per shard, up to 3
  skeptics per blocker/concern finding, and a synthesizer. For small changes,
  `/review` is the right tool.
- The artifact uses the same schema as `/review` (same `commit_hash` stamp), so
  the review-gate and Graphify treat it identically.
- The four principles live in `agents/karpathy-reviewer.md`; the panel reads them
  there (via `principlesPath`) rather than restating them.
