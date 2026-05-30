---
description: Session start ritual — load review history and graph context before working
---

Run this at the start of every working session in a project that uses boris-karpathy-loop. This is the connective tissue between sessions: it makes prior reviews and graph context part of how Claude approaches today's task.

## Steps

1. **Reviews.** If `reviews/` exists, read each review file's front-matter `status:` — **this is the source of truth, not `_index.md`'s prose.** List findings whose review is `status: open`, with file references. If `_index.md` disagrees with any front-matter `status:` (a review reads `open` in its file but `_index` shows it resolved, or the reverse), that is **status-drift** — surface it and suggest `/review-review` to reconcile.
2. **Graph.** If `graphify-out/GRAPH_REPORT.md` exists, read it. Note the commit hash it was built from.
3. **Drift check.** (a) *Graph:* compare the graph commit hash to `git rev-parse HEAD`; if they differ by more than ~5 commits, mention the graph may be stale and suggest running `/graphify . --update`. (b) *Reviews:* for each `status: open` review, compare its `commit_hash` to HEAD; if the cited code has moved many commits on, it is a **stale-open candidate** — the fix may have shipped without the status being flipped (a *false-open*, the mirror of the false-close). Suggest `/review-review` to reconcile.
4. **Anti-patterns.** If a globally-installed `the-boris-cherny-way` guides directory is referenced, optionally surface relevant entries from `guides/anti-patterns.md`.
5. **State explicitly to the user**, in this format:

   ```
   Loop context loaded:
   • <N> open review findings (most recent: <date>, <feature>)
   • Graph snapshot from <short hash> (<X commits behind / current>)
   • Anti-patterns potentially relevant: <list or "none surfaced">
   • <only if detected> ⚠ status-drift: <review> reads <status> but <evidence> — run /review-review

   Ready for today's task.
   ```

6. Wait for the user's task before doing any work.

## When nothing exists

If neither `reviews/` nor `graphify-out/` exists, output a brief note:

> This project has no review history or graph yet. Consider running `/review` after meaningful changes, and `graphify .` once to seed the graph. The loop compounds — start cheap.

Then proceed normally.

## Anti-pattern

Do not turn this into a long preamble. Three lines of context is enough; the user has work to do.
