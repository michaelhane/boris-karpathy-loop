---
description: Run Karpathy review on uncommitted changes (or a specified commit range)
---

Use the `karpathy-reviewer` subagent to review changes in the current repository.

## Steps

1. Run `git status --short` and `git diff HEAD` to detect uncommitted changes.
2. If there are no uncommitted changes:
   - Ask the user whether to scope to a commit range (e.g. `HEAD~3..HEAD`) or skip.
   - If they specify a range, pass it to the subagent. Otherwise stop.
3. Invoke the `karpathy-reviewer` subagent with the diff content and any user-provided context.
4. Wait for the subagent to write its review file under `reviews/`.
5. Display only the short summary the subagent printed inline.
6. Do NOT auto-fix anything based on findings. The user decides whether to address them.

## Notes

- This command is for meaningful changes. For typo fixes or single-line edits, just commit.
- If the user runs `/review` repeatedly on the same diff, do not re-review — point them to the existing review file.
- The review file is meant to be committed with the code so the team and Graphify see it.
