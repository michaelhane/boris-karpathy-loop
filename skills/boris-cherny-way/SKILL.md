---
name: boris-cherny-way
description: Apply Boris Cherny-style Claude Code workflow discipline. Maintain PROJECT_STATE.md and CHANGELOG.md across sessions, capture patterns and anti-patterns in a guides/ folder, and treat Claude as a junior engineer with perfect recall. Make sure to use this skill whenever working in a project that uses CLAUDE.md plus PROJECT_STATE.md, when starting or ending a session, or whenever there is an opportunity to capture a pattern that would compound across future sessions.
---

# The Boris Cherny Way

A workflow skill that captures Boris Cherny-style discipline for productive Claude Code sessions. Distilled from the `the-boris-cherny-way` knowledge base.

**Core philosophy:** Claude is a junior engineer with perfect recall — give it structure, log decisions, compound across sessions.

## When to apply this skill

- Starting a Claude Code session in a project that has CLAUDE.md / PROJECT_STATE.md
- Ending a session — close the loop
- Hitting an unexpected behavior or pattern worth capturing
- Reviewing a project's documentation hygiene
- Whenever the user mentions PROJECT_STATE, CHANGELOG, sessielog, /ctx, or "boris way"

## Session rituals

### Start of session

Simulate `/ctx` if no command exists:

1. Read project's CLAUDE.md.
2. Read PROJECT_STATE.md if it exists — the live status.
3. Skim recent CHANGELOG.md entries — what was done last session.
4. Generate a short TODO list for the current session based on PROJECT_STATE.
5. State the current goal explicitly before any code touches keys.

If `loop-bootstrap` command is also installed (boris-karpathy-loop), run that too — it loads review findings and graph context on top.

### During session

- Capture insights inline — don't postpone to "end of session", they evaporate.
- New patterns: write a concrete example into the relevant guide.
- New anti-patterns: write WHY it doesn't work, not just what doesn't work.
- Surface uncertainties with the user, don't paper over them.

### End of session

1. Update PROJECT_STATE.md with progress and next steps.
2. Append to CHANGELOG.md:
   - What was done
   - What was learned
   - What's next
3. If patterns emerged: update the relevant `guides/` file.

## File conventions

```
project/
├── CLAUDE.md              # entry point — references guides/, doesn't duplicate
├── PROJECT_STATE.md       # live status, refreshed each session
├── CHANGELOG.md           # append-only log of learnings
└── guides/
    ├── prompting.md       # what works for this project's prompts
    ├── workflows.md       # proven multi-step flows
    ├── debugging.md       # gotchas + fixes
    └── anti-patterns.md   # what NOT to do, with reasoning
```

## Principles

1. **Markdown-first.** Everything readable without tooling.
2. **Concrete over abstract.** A worked example beats a rule.
3. **Anti-patterns get reasoning.** "Don't X" is useless without "because Y".
4. **Compound gains.** Small captures across sessions become a moat.
5. **Single source of truth.** CLAUDE.md points to guides/, doesn't duplicate.

## Common gotchas

- **Out-of-date PROJECT_STATE.md** — agent acts on stale assumptions. Treat update as non-optional at session end.
- **Duplicated truth** — same rule in CLAUDE.md and a guide diverges over time. Keep CLAUDE.md as a pointer.
- **Anti-pattern collection rot** — entries pile up without review. Quarterly: prune resolved ones, promote durable ones.
- **Treating sessielog as documentation** — it's a journal, not a guide. Real learnings get extracted into `guides/`.

## Pairs well with

- `karpathy-reviewer` subagent — captures coding-time findings that feed `guides/anti-patterns.md` over time.
- `graphify` CLI — indexes `guides/` so future sessions can query the knowledge base structurally.

## Attribution

Inspired by the pragmatic Claude Code style associated with Boris Cherny (Anthropic engineer). This skill is a workflow distillation — Boris Cherny has not endorsed or contributed to this content.
