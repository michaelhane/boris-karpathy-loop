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
| Hook fixer (Windows) | `scripts/fix_graphify_hook.py` | Patch the graphify post-commit hook so it refreshes the graph reliably on Windows (idempotent; re-run after `graphify hook install`) |
| Review gate (hook) | `hooks/review_gate.py`, `hooks/review_gate.sh` | `PreToolUse` gate — warn/ask/block when a merge/push lands must-review code on master without a fresh review (opt-in per project) |
| Gate config example | `hooks/review-gate.example.json` | Copy to `.claude/review-gate.json` to opt a project in |

## Review gate (opt-in)

The loop is only as strong as the discipline to run `/review` before code lands
on master — and that discipline fails exactly under pressure (parallel sessions,
a deadline, a master collision). The **review gate** makes it visible. It is a
`PreToolUse` hook: when a `git merge` or `git push` is about to land changes to a
path you declared *must-review* on a master branch, **and there is no fresh
review for that diff in `reviews/`**, the gate surfaces a warning (or asks, or
blocks — your call).

It is a **floor, not a ceiling.** It checks *that* a review exists for the diff
(by matching the review's `commit_hash`), not that the review is any good.

**Safe-by-default and opt-in.** The plugin ships with the gate OFF. It does
nothing until a project drops a `.claude/review-gate.json` (copy
`hooks/review-gate.example.json` as a starting point):

```json
{
  "enabled": true,
  "mode": "ask",
  "must_review": [
    "scripts/sync_onbetaalde_facturen.py",
    "src/triage_ledger.py",
    "src/matching/**"
  ],
  "master_branches": ["master", "main"],
  "reviews_dir": "reviews",
  "log_path": ".claude/review-gate-log.jsonl"
}
```

| Field | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Master switch. Absent file or `false` ⇒ the gate is silent. |
| `mode` | `"warn"` | `warn` surfaces and proceeds; `ask` requires confirmation; `block` denies. Use `ask`/`block` for money-critical scope. |
| `must_review` | `[]` | Repo-root-relative globs. Empty ⇒ silent. The gate acts only on these. |
| `master_branches` | `["master","main"]` | Branches treated as "master". |
| `reviews_dir` | `"reviews"` | Where the loop's review files live. |
| `log_path` | `.claude/review-gate-log.jsonl` | Every fire and every bypass is appended here. |

**Bypass is allowed, but logged.** The gate never silently hard-blocks — that
just invites `--no-verify`. To proceed past a fire, set `REVIEW_GATE_BYPASS=1`:
the merge/push goes through and the bypass is recorded to the log. The honest fix
is to run `/review` so a review stamps the commit you are about to land.

**What it does *not* do.** Presence-check, not quality-check. It gates the
merge/push convergence point, not every commit. And it only sees git commands
Claude runs through the Bash tool — a `git merge` you type directly in your own
terminal is invisible to it (that would need an installed git
`pre-merge-commit`/`pre-push` hook; see the `review-gate` guide in
`the-boris-cherny-way`). On any internal error or undeterminable diff it
**fails open** — a broken gate must never block your work.

> The hook loads when the plugin is enabled at session start; the
> `.claude/review-gate.json` config is read fresh on every invocation, so edits
> to scope or mode take effect immediately — no restart needed.

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
- v0.2 — `/setup-graphify` + `/diagnose-loop` (operational commands encoding day-one dogfood lessons)
- v0.2.x — surgical fixes from in-loop review (tutor MC drift, `/loop-bootstrap` branch-mix, `/review` content-type judgment, naming-polish nits)
- v0.3 — **review-gate hook** (opt-in merge/push-to-master review floor); next: severity threshold tuning, `/tutor` learning-log review
- v0.3.x — review-gate git-hook variant (catch merges typed directly in a terminal, not just Claude-driven ones)
- v0.4 — tighter Graphify integration: review and learning files as typed graph nodes
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
