---
description: Health check for boris-karpathy-loop + graphify in the current project — report problems and exact fix commands; never auto-fix
---

Run when something feels wrong with the loop but you don't know what. This command is **read-only**: it diagnoses, prints fix commands, and stops. Mirrors `karpathy-reviewer`'s "Report only. Never auto-fix." discipline.

## Mindset

- Report findings; never modify anything.
- For each finding: one-line explanation + a concrete fix command the user can copy-paste.
- If everything is healthy, say so explicitly and exit. Do not invent issues.
- Order findings by priority at the end.

## Steps

Run all checks. Each emits ✅ / ⚠️ / ❌ + context.

### 1. Stale `claude` processes

Count running processes:
- Windows: `Get-Process claude -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count`
- macOS/Linux: `pgrep -c claude` (returns count) or `pgrep claude | wc -l`

If count > 5: ⚠️ stale processes can cache old env state — newly-set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` won't be picked up by an already-running shell.

Suggested fix:
- Windows: `Get-Process claude | Stop-Process -Force`
- macOS/Linux: `pkill claude`

### 2. Auth conflict (claude.ai login + API key both present)

- File: `~/.claude/.credentials.json` exists?
  - Windows: `Test-Path "$env:USERPROFILE\.claude\.credentials.json"`
  - macOS/Linux: `test -f "$HOME/.claude/.credentials.json"`
- Env var: `ANTHROPIC_API_KEY` set?

If **both** are true: ❌ auth conflict. Claude Code may prefer one over the other inconsistently across versions, leading to 401s or silent fallback to a wrong identity.

Suggested fix (official path first, env-var path as fallback):

```
# Inside claude:
/logout
# Then re-login and answer "No" when asked about API key approval.
```

If that doesn't resolve it, fallback (Windows):
```
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")
```

### 3. graphifyy install integrity

Run `uv tool list`, parse for `graphifyy`. If absent: ❌ graphify is not installed. Suggested fix:
```
uv tool install graphifyy --with anthropic --with openai
```

If present but extras are not visible in `uv tool list`, try `uv tool show graphifyy` to confirm `anthropic` and `openai` are in the install. If either is missing: ⚠️ multi-backend support will fail. Fix:
```
uv tool install graphifyy --reinstall --with anthropic --with openai
```

### 4. API keys

For each of `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`:
- Check presence (User-scope and current-shell). **Never echo the value.**
- Detect placeholder typos: if the value is the literal string `AIza...`, `sk-ant-...`, `sk-...`, or contains a `...` ellipsis, flag as placeholder rather than real key.
- For `GEMINI_API_KEY`: a real key starts with `AIzaSy` and is ~39 characters. If it starts with `AIza...` (literally with the trailing dots), it's the docs placeholder, not the real key.

If **none** of the three is set: ❌ nothing will work. Suggested fix:
```
# pick the backend you want, then:
$env:GEMINI_API_KEY = "<real key from aistudio.google.com/apikey>"
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $env:GEMINI_API_KEY, "User")
```
Both lines are required — first sets it for the current shell, second persists across new shells.

If a placeholder is detected: ❌ that key is unusable. Same fix command.

### 5. Hook status

Run `graphify hook status`. Parse output for `post-commit: installed` and `post-checkout: installed`.

If either missing: ⚠️ graph won't auto-rebuild after commits or branch switches. Suggested fix:
```
graphify hook install
graphify hook status   # re-verify
```

### 6. Project file presence

In the current project directory:

| File | Means |
|---|---|
| `.claude/settings.json` | graphify Claude integration installed |
| `graphify-out/graph.json` | graph extraction has run at least once |
| `graphify-out/GRAPH_REPORT.md` | `graphify cluster-only .` has run after extract |

For each missing file: ⚠️ + the exact step that would create it:
- `.claude/settings.json` missing → `graphify claude install`
- `graphify-out/graph.json` missing → `graphify extract . --backend <gemini|claude|ollama>`
- `graphify-out/GRAPH_REPORT.md` missing → `graphify cluster-only .` (uses existing graph, no extra LLM cost)

If `graph.json` exists but is suspiciously small (<50 KB) or `cluster-only` was run on a partial extract, mention that the cache may be masking a previous failure — `graphify extract` output should be re-checked for `chunk X/Y failed` lines.

### 7. Spook-CLAUDE.md in user home

- Windows: `Test-Path "$env:USERPROFILE\CLAUDE.md"`
- macOS/Linux: `test -f "$HOME/CLAUDE.md"`

(Note: this is `~/CLAUDE.md`, NOT `~/.claude/CLAUDE.md` — the latter is intentional.)

If present: ❌ Claude Code does directory walk-up from `cwd`; a file at the home root contaminates every project below it. Suggested fix:
```
# Windows
Remove-Item "$env:USERPROFILE\CLAUDE.md"

# macOS/Linux
rm "$HOME/CLAUDE.md"
```

## Output format

Section header per check, color-coded if the terminal supports it. For each issue: one-line explanation + the fix command in a code block.

### When everything is healthy

If no findings: print exactly this and exit:

> Loop healthy. Plugin installed, graphify integrated, hooks active, all keys valid, no spook files. No action needed.

### When findings exist

End with a single suggested next-step in priority order:

1. ❌ findings first (broken state) — pick the highest-impact one
2. ⚠️ findings next (working but degraded)
3. Stale processes / spook files last (hygiene)

Example:

> 3 issues found. Suggested order:
> 1. Resolve auth conflict (`/logout` then re-login).
> 2. Reinstall graphifyy with extras.
> 3. Run `graphify cluster-only .` to generate the missing report.

## Anti-patterns in your own behavior

- Do NOT modify anything. Reading files, running status commands, parsing output is fine. Writing, deleting, killing, installing — never.
- Do NOT echo API key values, ever. Even masked. Presence-only.
- Do NOT recommend a fix command without first confirming the issue exists.
- Do NOT chain fix commands into a single "run this and you're done" block. Each finding is independent; let the user choose order.
- Do NOT report ✅ for a check that errored — if a command failed (e.g. `graphify hook status` returned non-zero), surface that as ⚠️ and propose how to investigate.
- Do NOT review architectural choices. This is a health check, not `/review`.
