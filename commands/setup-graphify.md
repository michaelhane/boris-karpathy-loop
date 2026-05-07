---
description: Walk through enabling boris-karpathy-loop + graphify in the current project — detect state, prompt for choices, execute each step with explicit confirmation
---

Use this in a project where you want the loop active but graphify isn't yet set up. The command is **interactive** — it never modifies anything without explicit user confirmation per step.

## Refuse to run in unsafe locations

Resolve the current working directory. Abort with a clear message if it equals the user home directory:
- Windows: `$env:USERPROFILE`
- macOS/Linux: `$HOME`

A graphify install in home creates a "spook-CLAUDE.md" that contaminates every project via directory walk-up. If `cwd` matches home, output:

> Refused: this command must run inside a specific project directory, not the user home root. `cd` into a project first.

Then stop.

## Steps

### 1. Detect current state

Run all checks first; do **not** modify anything yet. Report results to the user.

> Note on naming: the package on PyPI / installed via `uv` is **graphifyy** (two y's); the CLI binary on PATH is **graphify** (one y). Don't "fix" one to match the other.

| Check | How |
|---|---|
| Graphify Claude integration | `.claude/settings.json` exists |
| Graph extracted | `graphify-out/graph.json` exists |
| Graph report present | `graphify-out/GRAPH_REPORT.md` exists (cluster-only has run) |
| Graphify section in CLAUDE.md | grep `CLAUDE.md` for `graphify` |
| API keys in env | check `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY` — **presence only**, never echo values |
| graphifyy installed with extras | `uv tool list --show-with` — output includes `[with: anthropic, openai]` for a fully-equipped install |
| Hooks installed | `graphify hook status` reports `installed` for post-commit and post-checkout |
| Spook-CLAUDE.md in home | `Test-Path $env:USERPROFILE/CLAUDE.md` (Win) / `test -f $HOME/CLAUDE.md` — warn if found |

Show each check as ✅ / ⚠️ / ❌ with one-line context.

### 2. Prompt for open decisions

Only ask questions detection couldn't answer:

- **Backend** (gemini / claude / ollama). Default suggestion logic:
  - `GEMINI_API_KEY` set → gemini
  - else `ANTHROPIC_API_KEY` set → claude
  - else no default — prompt explicitly
- **Project size warning**: if source-file count > 50 and chosen backend = `claude`, warn that Anthropic tier 1 caps at 30K tokens/min and may rate-limit; suggest gemini.
- **Commit `graphify-out/cache/`?** Default no — adds many small files. If no, plan to append `graphify-out/cache/` to `.gitignore` later.

Confirm chosen values back to the user before executing anything.

### 3. Estimate cost before any LLM call

Count source files (`.md`, `.py`, `.ts`, `.js`, `.go`, `.rs`, etc.). Exclude `node_modules/`, `.git/`, `graphify-out/`, `.venv/`.

Show estimate based on chosen backend:
- **gemini**: ~$0.05–0.20 per 50 files
- **claude**: ~$0.20–0.50 per 50 files
- **ollama**: free, slower

Wait for explicit user confirmation before spending tokens.

### 4. Execute steps in order, with confirmation between each

For each step: state what will run and why, wait for an explicit "go" / "y" / "ok" before running. If the user declines a step, skip it and continue.

1. **Add backend SDKs to graphifyy** (only if missing extras):
   ```
   uv tool upgrade graphifyy --with anthropic --with openai
   ```
   `upgrade --with` adds the missing extras without forcing a version change. Reserve `install --reinstall` for the case where the tool itself is corrupt; do not use it just to add extras, since it silently bumps the user to latest.
2. **Install graphify Claude integration** (only if `.claude/settings.json` missing):
   ```
   graphify claude install
   ```
   Adds a CLAUDE.md section + PreToolUse hook. **Re-check `cwd` before this step** as a safety net — `cd` mid-session could have moved cwd into home.
3. **Extract graph** (only if `graphify-out/graph.json` missing):
   ```
   graphify extract . --backend <chosen>
   ```
   After completion, scan output (case-insensitive) for any line containing `chunk` AND (`fail` OR `error`) — the exact phrasing varies between graphify versions, so do not match a literal string. If found, surface them — graphify writes partial graph.json on failure and the cache will mask it on later runs. Do not proceed to step 4 with an obviously failed extract.
4. **Generate report and visualization** (always run after extract — `extract` is headless):
   ```
   graphify cluster-only .
   ```
   No extra LLM cost; uses existing `graph.json`. Skipping this is the most common reason `GRAPH_REPORT.md` is missing.
5. **Install hooks** (only if `graphify hook status` showed missing):
   ```
   graphify hook install
   ```
6. **Verify hooks**:
   ```
   graphify hook status
   ```
   Parse output. Both `post-commit` and `post-checkout` must show `installed`. If either is missing, flag it and stop — don't paper over hook failure.
7. **Update `.gitignore`** if the user opted out of committing cache:
   - Append `graphify-out/cache/` (create `.gitignore` if absent).
8. **Stage** the new artifacts:
   ```
   git add graphify-out/ .claude/settings.json CLAUDE.md
   ```
   Add `.gitignore` if it was modified.
9. **Suggest commit message** (do not run `git commit` automatically):
   ```
   chore: enable boris-karpathy-loop with graphify (<backend> backend)
   ```
   Hand the commit to the user.

### 5. Final summary

Output:
- What was done — each step that ran, with status
- What was skipped — and why (already present, or user declined)
- Final state — what is and isn't configured now
- Suggested next: open a fresh `claude` session in this project, run `/loop-bootstrap`

## Anti-patterns in your own behavior

- Do NOT run any step without explicit confirmation. The command **walks** the user through; it does not drive.
- Do NOT echo API key values, ever. Presence-only checks; report `set` / `not set` / `looks like placeholder (e.g. literal "AIza...")`.
- Do NOT assume `extract` succeeded based on exit code alone. Always scan output (case-insensitive) for `chunk` + (`fail` OR `error`) on the same line.
- Do NOT skip `graphify cluster-only` after `extract` — they are two separate steps, not one.
- Do NOT run `graphify claude install` in the user home directory. The entry guard catches one case but re-check `cwd` immediately before that step.
- Do NOT auto-`git commit`. Stage and propose the message; the human types `git commit`.

## Cross-platform notes

This command runs in whatever shell the user has. Detect platform first (PowerShell on Windows vs bash on macOS/Linux) and use the matching commands:

- Path tests: `Test-Path X` vs `test -f X` / `test -d X`
- Home directory: `$env:USERPROFILE` vs `$HOME`
- Env-var lookup: `[Environment]::GetEnvironmentVariable("X","User")` vs `echo $X`

When in doubt, fall back to a Python or Node one-liner (`python -c "import os; print(os.path.expanduser('~'))"`) for portability.
