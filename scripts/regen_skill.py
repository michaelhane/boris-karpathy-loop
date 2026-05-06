#!/usr/bin/env python3
"""
regen_skill.py — regenerate skills/boris-cherny-way/SKILL.md from the
the-boris-cherny-way submodule's guides.

The KB updates over time (new Claude Code versions, new patterns). This script
keeps the plugin's skill content in sync with the current state of the KB
without requiring manual rewriting.

Workflow:
    git submodule update --remote the-boris-cherny-way
    python scripts/regen_skill.py
    git diff skills/boris-cherny-way/SKILL.md   # review changes
    git add . && git commit -m "chore: sync skill with KB"

Usage:
    python scripts/regen_skill.py [--kb-dir PATH] [--target PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

SKILL_TEMPLATE = """---
name: boris-cherny-way
description: Apply Boris Cherny-style Claude Code workflow discipline. Maintain PROJECT_STATE.md and CHANGELOG.md across sessions, capture patterns and anti-patterns in a guides/ folder, and treat Claude as a junior engineer with perfect recall. Make sure to use this skill whenever working in a project that uses CLAUDE.md plus PROJECT_STATE.md, when starting or ending a session, or whenever there is an opportunity to capture a pattern that would compound across future sessions.
---

# The Boris Cherny Way

A workflow skill that captures Boris Cherny-style discipline for productive
Claude Code sessions. Distilled from the `the-boris-cherny-way` knowledge base.

**Core philosophy:** Claude is a junior engineer with perfect recall — give it
structure, log decisions, compound across sessions.

> Synced from KB on {sync_date}. Source guides: {guide_count}. To regenerate:
> `python scripts/regen_skill.py`

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
{guide_listing}
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
- `karpathy-tutor` subagent — deep teaching when you want to actually learn something instead of just shipping it.
- `graphify` CLI — indexes `guides/` so future sessions can query the knowledge base structurally.

## Attribution

Inspired by the pragmatic Claude Code style associated with Boris Cherny
(Anthropic engineer). This skill is a workflow distillation — Boris Cherny
has not endorsed or contributed to this content.
"""

H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def discover_guides(kb_dir: Path) -> list[tuple[str, str]]:
    """Return (filename, one-line description) for each .md in kb_dir/guides."""
    guides_dir = kb_dir / "guides"
    if not guides_dir.is_dir():
        return []
    out: list[tuple[str, str]] = []
    for f in sorted(guides_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = H1_RE.search(text)
        title = m.group(1).strip() if m else f.stem
        out.append((f.name, title))
    return out


def render_guide_listing(guides: list[tuple[str, str]]) -> str:
    if not guides:
        return "│   └── (no guides yet — start writing them)"
    lines = []
    for i, (filename, title) in enumerate(guides):
        connector = "└──" if i == len(guides) - 1 else "├──"
        lines.append(f"│   {connector} {filename:<24} # {title}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kb-dir", type=Path, default=Path("the-boris-cherny-way"))
    p.add_argument(
        "--target",
        type=Path,
        default=Path("skills/boris-cherny-way/SKILL.md"),
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.kb_dir.is_dir():
        print(
            f"KB directory {args.kb_dir} not found. "
            "Did you run `git submodule update --init`?",
            file=sys.stderr,
        )
        return 1

    guides = discover_guides(args.kb_dir)
    rendered = SKILL_TEMPLATE.format(
        sync_date=date.today().isoformat(),
        guide_count=len(guides),
        guide_listing=render_guide_listing(guides),
    )

    if args.dry_run:
        print(rendered)
        return 0

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {args.target} ({len(rendered)} bytes, "
        f"{len(guides)} guides referenced)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
