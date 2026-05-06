---
description: Session start ritual — load review history and graph context before working
---

Run this at the start of every working session in a project that uses boris-karpathy-loop. This is the connective tissue between sessions: it makes prior reviews and graph context part of how Claude approaches today's task.

## Steps

1. **Reviews.** If `reviews/_index.md` exists, read it. List open findings with file references.
2. **Graph.** If `graphify-out/GRAPH_REPORT.md` exists, read it. Note the commit hash it was built from.
3. **Drift check.** Compare graph commit hash to `git rev-parse HEAD`. If they differ by more than ~5 commits, mention that the graph may be stale and suggest running `/graphify . --update`.
4. **Anti-patterns.** If a globally-installed `the-boris-cherny-way` guides directory is referenced, optionally surface relevant entries from `guides/anti-patterns.md`.
5. **State explicitly to the user**, in this format:

   ```
   Loop context loaded:
   • <N> open review findings (most recent: <date>, <feature>)
   • Graph snapshot from <short hash> (<X commits behind / current>)
   • Anti-patterns potentially relevant: <list or "none surfaced">

   Ready for today's task.
   ```

6. Wait for the user's task before doing any work.

## When nothing exists

If neither `reviews/` nor `graphify-out/` exists, output a brief note:

> This project has no review history or graph yet. Consider running `/review` after meaningful changes, and `graphify .` once to seed the graph. The loop compounds — start cheap.

Then proceed normally.

## Anti-pattern

Do not turn this into a long preamble. Three lines of context is enough; the user has work to do.
