---
description: Invoke the Karpathy-style tutor — first principles, build-from-scratch, real code, no fluff
---

Use the `karpathy-tutor` subagent to teach the user something deeply. The user wants to *understand*, not just to be told.

## Steps

1. Detect what the user wants to learn. If they typed `/tutor` with a topic, that's the seed; if not, ask: **"What do you want to understand?"**
2. Pass the topic plus current project context (filenames they're looking at, recent files in `git status`) to the `karpathy-tutor` subagent.
3. Let the subagent run its diagnose → motivate → naïve → hurt → real → connect → verify loop.
4. When the subagent closes the session with the three-line footer (You can now / Try this / Next), display it cleanly.
5. If the user is using boris-karpathy-loop's learning log, the subagent will already have appended an entry. Don't duplicate.

## When NOT to use this

- For "how do I do X right now" — that's a coding question, not a learning question. Answer directly.
- For trivia ("what does this flag do") — a docs lookup is faster than a teaching session.
- When the user is mid-flow on shipping something. Teaching interrupts; offer to come back to it later.

## Suggested invocations

- `/tutor` — open-ended: tutor asks what to teach
- `/tutor attention mechanism in transformers`
- `/tutor why does this Supabase RLS policy fail`
- `/tutor explain my own code at src/games/lettergreep-springer/`
