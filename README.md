# boris-karpathy-loop

> A self-improving Claude Code workflow: Boris-style session discipline, Karpathy-inspired review and tutoring subagents, and a Graphify-friendly review log that compounds across sessions.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## What this is

Three layers, one loop, plus a tutor for the days you want to learn instead of ship:

```
   ┌──────────────────────────────────────────────┐
   │ Boris layer                                  │
   │   /ctx — session start                       │
   │   PROJECT_STATE.md, CHANGELOG.md             │
   │   guides/ as single source of truth          │
   └──────────────────────────────────────────────┘
                        │
                        ▼
   ┌──────────────────────────────────────────────┐
   │ Karpathy layer                               │
   │   /review — independent post-hoc review      │
   │   /tutor  — first-principles teaching        │
   │   Findings → reviews/, lessons → learning/   │
   └──────────────────────────────────────────────┘
                        │
                        ▼
   ┌──────────────────────────────────────────────┐
   │ Graphify layer (optional but recommended)    │
   │   Indexes guides/ + reviews/ as a graph      │
   │   Next session: /loop-bootstrap reads graph  │
   │   Compounding context across sessions        │
   └──────────────────────────────────────────────┘
```

The point isn't any single layer. It's the loop. Reviews become anti-patterns. Anti-patterns become guides. Guides become graph nodes. Tutor sessions log what you learned. The next session starts smarter than the last.

## Install

### As a Claude Code plugin (recommended)

```bash
/plugin marketplace add michaelhane/boris-karpathy-loop
/plugin install boris-karpathy-loop@boris-karpathy-loop
```

This makes `boris-cherny-way` (skill), `karpathy-reviewer` and `karpathy-tutor` (subagents), and `/review`, `/review-review`, `/loop-bootstrap`, `/tutor` (commands) available in every Claude Code session.

### Optional but recommended: pair with Graphify

```bash
uv tool install graphifyy
graphify claude install
```

In each project where you want compounding context:

```bash
graphify .
git add graphify-out/
graphify hook install
```

## Quick start in a project

```bash
cd your-project

# First time in this project: detect state, install graphify,
# wire up hooks, propose the initial commit. Refuses to run in $HOME.
/setup-graphify

# Session start: load past reviews, graph context, learning history
/loop-bootstrap

# Work. Boris session discipline kicks in via the skill.

# Want to actually understand something instead of just shipping it?
/tutor attention mechanism
/tutor my own code at src/games/lettergreep-springer/

# Completed a meaningful change? Before commit:
/review

# Periodically: re-evaluate stale findings
/review-review

# When something feels off — silent failures, missing keys,
# broken hooks, stale process state — read-only health check:
/diagnose-loop

# Promote durable findings into anti-patterns:
python scripts/extract_patterns.py \
    --reviews-dir reviews/ \
    --target guides/anti-patterns.md
```

## What's in the box

| Component | Path | Purpose |
|---|---|---|
| Workflow skill | `skills/boris-cherny-way/SKILL.md` | Always-on Boris session rituals |
| Review subagent | `agents/karpathy-reviewer.md` | Independent code review against 4 principles |
| Tutor subagent | `agents/karpathy-tutor.md` | First-principles, build-from-scratch teaching |
| `/review` | `commands/review.md` | Trigger reviewer on uncommitted changes |
| `/review-review` | `commands/review-review.md` | Re-evaluate stale findings |
| `/loop-bootstrap` | `commands/loop-bootstrap.md` | Session start — load reviews + graph + learning history |
| `/tutor` | `commands/tutor.md` | Invoke deep teaching mode |
| `/setup-graphify` | `commands/setup-graphify.md` | Per-project setup walk-through — detect state, prompt for choices, execute with confirmation |
| `/diagnose-loop` | `commands/diagnose-loop.md` | Read-only health check; reports issues + fix commands, never auto-fixes |
| Pattern extractor | `scripts/extract_patterns.py` | Promote closed findings into the anti-pattern guide |
| Skill regenerator | `scripts/regen_skill.py` | Sync `boris-cherny-way` skill from the KB (activates once KB is published) |

## Why three layers + a tutor

**Boris alone** captures discipline but no critique. The agent builds; nothing checks.

**Karpathy review alone** critiques but doesn't persist. Findings land in chat and evaporate.

**Karpathy tutor alone** teaches but doesn't connect to your real work. Synthetic exercises.

**Graphify alone** indexes but doesn't generate signal worth indexing.

Together: the agent builds, the reviewer scrutinizes, the tutor deepens understanding when shipping isn't the priority, the graph remembers, and the next session is smarter than the last. That is the loop.

## Keeping the skill in sync with the KB

The `boris-cherny-way` skill is distilled from a knowledge base maintained by
the author. KB sync via `scripts/regen_skill.py` activates once the KB is
published — currently the skill content is hand-curated.

## When to use this

Best fit:
- Multi-week projects where the agent should learn from its past mistakes
- Teams wanting shared review discipline without writing the rules from scratch
- Solo devs treating Claude Code as a junior engineer and wanting senior-level review
- Anyone who wants to actually *understand* the libraries and patterns they use, not just import them

Bad fit:
- One-off scripts and prototypes (the ceremony costs more than it saves)
- Tasks Claude can complete in a single edit (use judgment — `/review` for typo fixes is silly)

## Roadmap

- v0.1 — initial release: skill, two subagents, four commands, two scripts
- v0.2 — pre-commit hook, severity threshold tuning, `/tutor` learning-log review
- v0.3 — tighter Graphify integration: review and learning files as typed graph nodes
- v0.x — based on what dogfooding surfaces

## Sources & attribution

This plugin stands on others' work and aims to credit clearly.

- **Andrej Karpathy** — author of the [January 26, 2026 X post](https://x.com/karpathy) on LLM coding pitfalls (the four principles in the reviewer subagent are derived from his observations) and of widely-cited public teaching including cs231n, "Let's build GPT from scratch", "Intro to LLMs", and "Software 2.0" (the tutor subagent's pedagogy is observational interpretation of his style). Karpathy has not endorsed or contributed to this plugin.
- **Forrest Chang** — author of [`forrestchang/andrej-karpathy-skills`](https://github.com/forrestchang/andrej-karpathy-skills) (MIT License), the original CLAUDE.md that translated Karpathy's post into actionable Claude Code guidelines. The structure of the four-principle review draws on his work; the prose in this plugin's reviewer subagent is original.
- **Boris Cherny** — Anthropic engineer whose pragmatic Claude Code workflow inspired the discipline captured in `skills/boris-cherny-way/`. Boris has not endorsed or contributed to this plugin; the workflow distillation is observational and may not reflect his current views.
- **Safi Shamsi** — author of [`safishamsi/graphify`](https://github.com/safishamsi/graphify) (MIT License), which this plugin pairs with for cross-session context. Graphify is not bundled here — install it separately.
- **The `the-boris-cherny-way` knowledge base** — the source from which the workflow skill is distilled. Maintained by the author of this plugin; not yet public, so the skill content is hand-curated for now.

## License

MIT — see [LICENSE](LICENSE). Compatible with the upstream MIT licenses of `forrestchang/andrej-karpathy-skills` and `graphify`.

## Author

First publish. Feedback, issues, and PRs welcome.
