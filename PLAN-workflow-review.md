# `/workflow-review` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/workflow-review` command: a planner-driven, multi-agent Karpathy review panel that adaptively shards a diff, reviews each shard, adversarially verifies every finding, and writes one canonical `reviews/` artifact.

**Architecture:** A thin plugin command (`commands/workflow-review.md`) gathers the git scope + gate config and launches a Workflow-tool script (`workflows/workflow-review.js`). The script runs 5 phases — plan → review (fan-out) → adversarial verify → dedup (pure JS) → synthesize — and the synthesizer writes the canonical review file in the existing schema (commit_hash-stamped, so the review-gate + Graphify keep working). The four principles stay single-source in `agents/karpathy-reviewer.md`; reviewers read them at an absolute `principlesPath` passed in `args`.

**Tech Stack:** Claude Code plugin (markdown command + manifest), the `Workflow` orchestration tool (plain-JS script, no TS, no `Date.now`/`Math.random`), git, `claude plugin validate`.

**Spec:** [PRD-workflow-review.md](PRD-workflow-review.md). **Branch:** `feat/workflow-review` (already created; PRD committed at `26b6850`).

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `workflows/workflow-review.js` | Create | The 5-phase orchestration: meta, schemas, planner, review fan-out, adversarial verify, pure-JS dedup, synthesizer. One self-contained script. |
| `commands/workflow-review.md` | Create | Thin command: scope the diff, read gate config, capture date, launch the Workflow with `args`, print the returned summary. Degrades to `/review` if the Workflow tool is absent. |
| `.claude-plugin/plugin.json` | Modify | Register the command; bump `version` 0.3.2 → 0.4.0 (cache is version-gated — the bump is the delivery mechanism). |
| `README.md` | Modify | What's-in-the-box row, roadmap line, a `/workflow-review` section. |
| `CLAUDE.md` | Modify | One short project-note documenting the new command + where the script lives. |
| `COMMIT_PLAN.md` | Modify | A short Phase L pointer to this build. |

**Verification reality (read before Task 1):** these workflow scripts use top-level `await` and top-level `return`, which the Workflow runtime makes legal by wrapping the body. Plain `node --check` treats the file as a standalone ES module and **errors on the top-level return** — so `node --check` is NOT a valid syntax gate here. The real syntax/runtime gate is the first `/workflow-review` launch (Task 6); the Workflow tool reports script errors at launch. Manifest correctness is gated by `claude plugin validate .` (Task 3). Don't fabricate a `node` test step.

---

## Task 1: The Workflow orchestration script

**Files:**
- Create: `workflows/workflow-review.js`

- [ ] **Step 1: Create `workflows/workflow-review.js` with this exact content**

```javascript
export const meta = {
  name: 'workflow-review',
  description: 'Planner-driven multi-agent Karpathy review panel: plan -> fan-out -> adversarial verify -> dedup -> one canonical reviews/ artifact',
  phases: [
    { title: 'Plan', detail: 'one planner agent picks the shard strategy' },
    { title: 'Review', detail: 'one reviewer per shard, scoped to a principle/file lens' },
    { title: 'Verify', detail: 'adversarial skeptics try to refute each blocker/concern finding' },
    { title: 'Synthesize', detail: 'one agent writes the canonical review file' },
  ],
}

// ---- args (supplied by the /workflow-review command) ----
// { today, commitHash, range, scopeFiles, mustReview, reviewsDir, principlesPath }
const today = (args && args.today) || 'unknown-date'
const commitHash = (args && args.commitHash) || 'UNKNOWN'
const range = (args && args.range) || null            // null => uncommitted (git diff HEAD)
const scopeFiles = (args && args.scopeFiles) || null  // null => all changed files
const mustReview = (args && args.mustReview) || []
const reviewsDir = (args && args.reviewsDir) || 'reviews'
const principlesPath = (args && args.principlesPath) || 'agents/karpathy-reviewer.md'

const diffCmd = range ? `git diff ${range}` : 'git diff HEAD'
const numstatCmd = range ? `git diff --numstat ${range}` : 'git diff --numstat HEAD'
const nameOnlyCmd = range ? `git diff --name-only ${range}` : 'git diff --name-only HEAD'

const PRINCIPLE_NAMES = {
  1: "Don't assume - surface what was glossed over",
  2: 'Surgical changes - minimum viable diff',
  3: 'Preserve what works - no silent destruction',
  4: 'Goal-driven execution - verifiable success',
}

// ---- schemas ----
const PLAN_SCHEMA = {
  type: 'object',
  required: ['strategy', 'shards'],
  properties: {
    strategy: { type: 'string', enum: ['by-principle', 'by-file', 'matrix'] },
    shards: {
      type: 'array',
      items: {
        type: 'object',
        required: ['principles', 'files', 'why'],
        properties: {
          principles: { type: 'array', items: { type: 'integer', minimum: 1, maximum: 4 } },
          files: { type: 'array', items: { type: 'string' } },
          why: { type: 'string' },
        },
      },
    },
    caps_applied: { type: 'array', items: { type: 'string' } },
  },
}

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['principle', 'severity', 'file', 'line', 'title', 'why', 'suggested_resolution'],
        properties: {
          principle: { type: 'integer', minimum: 1, maximum: 4 },
          severity: { type: 'string', enum: ['BLOCKER', 'CONCERN', 'NIT'] },
          file: { type: 'string' },
          line: { type: 'integer' },
          title: { type: 'string' },
          why: { type: 'string' },
          suggested_resolution: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['refuted', 'reason'],
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
  },
}

// ---- pure-JS helpers ----
function dedupeFindings(findings) {
  const seen = new Set()
  const out = []
  for (const f of findings) {
    const key = `${(f.file || '').toLowerCase()}|${f.line || 0}|${f.principle}|${(f.title || '').trim().toLowerCase()}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(f)
  }
  return out
}

function tallySeverity(findings) {
  const c = { blocker: 0, concern: 0, nit: 0 }
  for (const f of findings) {
    if (f.severity === 'BLOCKER') c.blocker++
    else if (f.severity === 'CONCERN') c.concern++
    else if (f.severity === 'NIT') c.nit++
  }
  return c
}

// ---- Phase 1: Plan ----
phase('Plan')
const plan = await agent(
  `You are the PLANNER for a multi-agent code-review panel. Do NOT review the code yourself.
Run \`${diffCmd}\` and \`${numstatCmd}\` to see the change under review.
${scopeFiles ? `Scope is limited to these files: ${scopeFiles.join(', ')}.` : ''}
These repo-root globs are MUST-REVIEW (money/security/core) - treat any matching file as HIGH risk: ${mustReview.length ? mustReview.join(', ') : '(none configured)'}.

Choose a shard strategy:
- "by-principle": small diff (<= ~3 files / <= ~150 changed lines). Exactly 4 shards, one per Karpathy principle (1..4), each reviews the WHOLE diff.
- "by-file": many files, each moderate. One shard per file; each reviews that file against all 4 principles.
- "matrix": large AND risky. Heavy principle 3 (preserve-what-works, must inspect every deletion) sharded per file; light principles 1,2,4 one shard each over the whole diff.

Cap total shards at 8. If by-file/matrix would exceed 8, group files into <=8 buckets and record that in caps_applied.
For each shard return: principles (array of integers 1..4), files (array of repo-root paths, or ["*"] for the whole diff), and a one-line why.`,
  { phase: 'Plan', schema: PLAN_SCHEMA }
)

if (!plan || !plan.shards || !plan.shards.length) {
  log('Planner produced no shards - aborting without writing a review.')
  return { error: 'no-plan', summary: 'workflow-review: planner produced no shards; nothing was reviewed.' }
}
log(`Strategy: ${plan.strategy} - ${plan.shards.length} shards${plan.caps_applied && plan.caps_applied.length ? ' - caps: ' + plan.caps_applied.join('; ') : ''}`)

// ---- Phase 2 (Review) + Phase 3 (Verify), pipelined per shard ----
const reviewed = await pipeline(
  plan.shards,
  (shard, _orig, i) => {
    const lensList = shard.principles.map((p) => `${p} (${PRINCIPLE_NAMES[p] || '?'})`).join(', ')
    const scope = shard.files && shard.files[0] !== '*' ? `ONLY these files: ${shard.files.join(', ')}` : 'the whole diff'
    return agent(
      `You are an INDEPENDENT Karpathy code reviewer. You did NOT write this code.
First, Read the file at \`${principlesPath}\` and study ONLY these principle(s): ${lensList}. Use its "Look for" lists as your checklist - do not restate or invent principles.
Then run \`${diffCmd}\` and review ${scope} through ONLY those principle(s).
Be rigorous, not nice. If genuinely clean for your lens, return an empty findings array - do NOT invent findings to fill a quota.
Each finding: principle (one of ${shard.principles.join('/')}), severity (BLOCKER|CONCERN|NIT), file (repo-root path), line (number, or 0 if N/A), title (<=8 words), why (concrete impact), suggested_resolution (a direction, not a patch).`,
      { label: `review:shard${i + 1}`, phase: 'Review', schema: FINDINGS_SCHEMA }
    )
  },
  async (review, shard, i) => {
    if (!review || !review.findings) return { shardIndex: i, findings: [] }
    const kept = []
    for (const f of review.findings) {
      if (f.severity === 'NIT') {
        kept.push({ ...f, verified: 'nit-unverified' })
        continue
      }
      const skeptics = budget.total && budget.remaining() < 80000 ? 1 : 3
      const votes = await parallel(
        Array.from({ length: skeptics }, (_v, k) => () =>
          agent(
            `You are skeptic #${k + 1} trying to REFUTE a code-review finding. Default to refuted=true if uncertain.
Run \`${diffCmd}\` to inspect the actual change.
Finding - principle ${f.principle}, ${f.severity}: "${f.title}" at ${f.file}:${f.line}. Why claimed: ${f.why}.
Is this finding real and material to THIS diff, or is it wrong / overstated / not actually present? Return refuted (boolean) + a one-line reason.`,
            { label: `verify:s${i + 1}:${f.file}`, phase: 'Verify', schema: VERDICT_SCHEMA }
          )
        )
      )
      const refutes = votes.filter(Boolean).filter((v) => v.refuted).length
      const survived = refutes < Math.ceil(skeptics / 2)
      log(`${survived ? 'KEEP' : 'DROP'} [${f.severity}] ${f.title} (${f.file}:${f.line}) - ${refutes}/${skeptics} refuted`)
      if (survived) kept.push({ ...f, verified: `${skeptics - refutes}/${skeptics} upheld` })
    }
    return { shardIndex: i, findings: kept }
  }
)

// ---- Phase 4: Dedup (pure JS, no agent) ----
const allFindings = reviewed.filter(Boolean).flatMap((r) => r.findings)
const deduped = dedupeFindings(allFindings)
log(`${allFindings.length} findings survived verify -> ${deduped.length} after dedup`)

// ---- Phase 5: Synthesize ----
phase('Synthesize')
const counts = tallySeverity(deduped)
const summary = await agent(
  `You are the SYNTHESIZER for a Karpathy review panel. Do NOT fix anything - report only.
Run \`${nameOnlyCmd}\` to get the list of touched files.
Use the Write tool to create \`${reviewsDir}/${today}-<feature-slug>.md\` (derive a short kebab-case feature-slug from the change). The Write tool creates parent directories.
Use EXACTLY this template:

---
date: ${today}
feature: <feature-slug>
commit_hash: ${commitHash}
files_touched:
  - <repo-root path>
severity_summary:
  blocker: ${counts.blocker}
  concern: ${counts.concern}
  nit: ${counts.nit}
status: open
verification_needed:
  - <thing to verify before considering this done>
review_method: "workflow-review (${plan.strategy}, ${plan.shards.length} shards${plan.caps_applied && plan.caps_applied.length ? ', caps: ' + plan.caps_applied.join('; ') : ''})"
---

# Review: <feature title>

## Context
<one paragraph: what the change was trying to do>

## Findings
(one block per finding below, grouped by severity, blockers first; if there are zero findings, write "None - clean for all reviewed principles.")

### [SEVERITY] <one-line title>
- **Principle:** <1-4>
- **Where:** path:line
- **Why it matters:** <impact>
- **Suggested resolution:** <a direction, not a fix>

## What was done well
<brief, honest>

The findings to write (already adversarially verified + deduped), as JSON:
${JSON.stringify(deduped, null, 2)}

After writing the review file, append ONE line to \`${reviewsDir}/_index.md\` (create the file if missing), matching the existing one-line format:
- ${today} \`<feature-slug>\` - ${counts.blocker} blockers, ${counts.concern} concerns, ${counts.nit} nits ([link](./${today}-<feature-slug>.md))

Then return EXACTLY this summary text and nothing else:
workflow-review: ${reviewsDir}/${today}-<feature-slug>.md
  - ${counts.blocker} blockers
  - ${counts.concern} concerns
  - ${counts.nit} nits
  - strategy: ${plan.strategy} (${plan.shards.length} shards)
Open the file for full details.`,
  { phase: 'Synthesize' }
)

return { summary, strategy: plan.strategy, shards: plan.shards.length, counts }
```

> **Post-dogfood correction (2026-07-11).** The first two real runs surfaced that
> the pipeline listing above bakes in the empty-on-error anti-pattern this panel
> is built to catch (its own principle P1). The **shipped** `workflows/workflow-review.js`
> supersedes the two spots below; do not copy the listing above verbatim:
> - **Stage-2 reviewer guard** (`if (!review) return {findings: []}`): a failed or
>   malformed reviewer was byte-identical to a clean lens, so a crashed shard read
>   as "clean". Fixed: return `{failed: true, lens}`, collect failed + null-dropped
>   shards, and force them into the artifact's `verification_needed`.
> - **Skeptic tally** (`votes.filter(Boolean)` over the requested `skeptics` count):
>   if every skeptic errored, `refutes=0` and the finding survived labeled
>   "3/3 upheld" — a verification that never ran. Fixed: judge over the votes that
>   actually returned; zero returns ⇒ keep but label "unverified", and the degraded
>   skeptic count is now visible per-finding in the `verified` field.

- [ ] **Step 2: Eyeball-review the script against the spec**

No automated syntax gate applies (see "Verification reality" above — `node --check` is invalid for these scripts). Confirm by eye:
- `export const meta` is a pure literal (no variables/calls). ✓ required by the Workflow tool.
- No `Date.now()` / `Math.random()` / `new Date()` anywhere. ✓ (date comes from `args.today`).
- Every `agent()` with a `schema` references a schema defined above it.
- `pipeline` stage signatures: stage 1 `(shard, _orig, i)`, stage 2 `(review, shard, i)`.
- Helpers `dedupeFindings` / `tallySeverity` are defined before the top-level `return`.

- [ ] **Step 3: Commit**

```bash
git add workflows/workflow-review.js
git commit -F - <<'EOF'
feat(workflow-review): add planner-driven multi-agent review panel script

5 phases: plan -> review fan-out -> adversarial verify -> dedup -> synthesize.
Reviewers read the 4 principles from an absolute principlesPath (passed in args)
so the panel works in any consuming project, not just this repo. Synthesizer
writes the existing reviews/ schema (commit_hash-stamped).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 2: The `/workflow-review` command

**Files:**
- Create: `commands/workflow-review.md`

- [ ] **Step 1: Create `commands/workflow-review.md` with this exact content**

````markdown
---
description: Heavy multi-agent Karpathy review panel — planner shards the diff, reviewers fan out, every blocker/concern is adversarially verified, one canonical review lands in reviews/
---

Run the **planner-driven review panel** for the current repository. This is the
heavy counterpart to `/review` — use it for large or risky changes, not typos.

## Steps

1. **Scope the diff.** Run:
   ```bash
   git rev-parse HEAD
   git status --short
   git diff HEAD --numstat
   ```
   - If `$ARGUMENTS` names a commit range (e.g. `HEAD~3..HEAD`) or a file set, scope to that instead.
   - If there are no uncommitted changes and no range was given, ask the user whether to scope to a range or stop. Do **not** launch the panel on an empty diff.

2. **Read the gate config (optional).** If `.claude/review-gate.json` exists, read its `must_review` array and pass it as risk hints. If absent, pass `[]`.

3. **Capture the date.** Run `date +%F`. The Workflow script cannot compute the date itself, so it must be passed in.

4. **Launch the panel.** Call the `Workflow` tool with:
   - `scriptPath`: `${CLAUDE_PLUGIN_ROOT}/workflows/workflow-review.js`
   - `args` (a JSON object):
     ```json
     {
       "today": "<output of date +%F>",
       "commitHash": "<output of git rev-parse HEAD>",
       "range": "<HEAD~3..HEAD, or null for uncommitted>",
       "scopeFiles": ["<path>", "..."],
       "mustReview": ["<glob>", "..."],
       "reviewsDir": "reviews",
       "principlesPath": "${CLAUDE_PLUGIN_ROOT}/agents/karpathy-reviewer.md"
     }
     ```
     Use `null` for `range` when reviewing uncommitted changes, and `null` for `scopeFiles` when reviewing every changed file.
   This command's instruction to call `Workflow` is the explicit opt-in the tool requires.

5. **Report.** When the workflow finishes, print the `summary` it returns — nothing more. Do not list every finding inline; the `reviews/` artifact is the source of truth.

6. **Do NOT auto-fix.** The panel reports only. The user decides what to act on.

## If the Workflow tool is unavailable

Some environments don't expose the `Workflow` tool. If you cannot call it, say so
plainly and offer to run `/review` (the single-agent path) instead. Do **not**
silently fall back, and do not try to re-implement the panel by hand.

## Notes

- Heavy by design: the panel spawns a planner, one reviewer per shard, up to 3
  skeptics per blocker/concern finding, and a synthesizer. For small changes,
  `/review` is the right tool.
- The artifact uses the same schema as `/review` (same `commit_hash` stamp), so
  the review-gate and Graphify treat it identically.
- The four principles live in `agents/karpathy-reviewer.md`; the panel reads them
  there (via `principlesPath`) rather than restating them.
````

- [ ] **Step 2: Commit**

```bash
git add commands/workflow-review.md
git commit -F - <<'EOF'
feat(workflow-review): add /workflow-review command

Thin launcher: scopes the diff, reads the gate's must_review hints, captures the
date, then calls the Workflow tool with workflow-review.js. Degrades to /review
when the Workflow tool is unavailable; never silently falls back.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 3: Register the command + bump the version

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Add the command to the `commands` array and bump `version`**

In `.claude-plugin/plugin.json`, change `"version": "0.3.2"` to `"version": "0.4.0"`, and add `"./commands/workflow-review.md"` as the last entry of the `commands` array. The result:

```json
{
  "name": "boris-karpathy-loop",
  "version": "0.4.0",
  "description": "Boris-style workflow discipline plus Karpathy-inspired review and tutoring subagents. Findings and lessons land on disk for cross-session learning. Designed to compound with Graphify-indexed knowledge.",
  "author": {
    "name": "michaelhane",
    "url": "https://github.com/michaelhane"
  },
  "license": "MIT",
  "homepage": "https://github.com/michaelhane/boris-karpathy-loop",
  "skills": [
    "./skills/boris-cherny-way"
  ],
  "agents": [
    "./agents/karpathy-reviewer.md",
    "./agents/karpathy-tutor.md"
  ],
  "commands": [
    "./commands/review.md",
    "./commands/review-review.md",
    "./commands/loop-bootstrap.md",
    "./commands/tutor.md",
    "./commands/setup-graphify.md",
    "./commands/diagnose-loop.md",
    "./commands/workflow-review.md"
  ],
  "hooks": "./hooks/hooks.json"
}
```

(There is no `workflows` manifest field — the script is referenced by path from the command, not registered.)

- [ ] **Step 2: Validate the manifest against the schema**

Run: `claude plugin validate .`
Expected: `plugin.json` and `marketplace.json` both pass schema validation (no errors).

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -F - <<'EOF'
feat(workflow-review): register /workflow-review, bump to v0.4.0

Cache is version-gated, so the bump is the delivery mechanism for the new
command. Graphify-typed-nodes milestone shifts from v0.4 to v0.5.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 4: Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `COMMIT_PLAN.md`

- [ ] **Step 1: README — add a row to the "What's in the box" table**

Add this row to the component table (after the `/diagnose-loop` row):

```markdown
| `/workflow-review` | `commands/workflow-review.md` + `workflows/workflow-review.js` | Heavy multi-agent review panel — planner shards the diff, reviewers fan out, every blocker/concern is adversarially verified, one canonical review lands in `reviews/` |
```

- [ ] **Step 2: README — add a section after the "Review gate (opt-in)" section**

```markdown
## `/workflow-review` — the multi-agent review panel

`/review` is one agent walking four principles in sequence and certifying its own
findings. `/workflow-review` is the heavy counterpart for large or risky changes:

1. A **planner** reads the diff (and the gate's `must_review` globs) and picks a
   shard strategy — `by-principle` for small diffs, `by-file` for many files,
   `matrix` (principle × file) for large, risky ones.
2. Reviewers **fan out** per shard, each reading its principle(s) from
   `agents/karpathy-reviewer.md` (single source of truth) and reporting findings
   as data.
3. Every **blocker/concern** is **adversarially verified** — three skeptics try to
   refute it; a majority refutation drops it. (Nits pass through unverified.)
4. Findings are **deduped** (pure code) and a **synthesizer** writes one review in
   the exact `reviews/` schema — same `commit_hash` stamp, so the review-gate and
   Graphify treat it identically.

It is **opt-in and heavy** — it spawns a planner, one reviewer per shard, up to
three skeptics per finding, and a synthesizer. For small changes, use `/review`.
Whatever the planner caps (shards grouped, skeptics reduced under a tight token
budget) is recorded in the review artifact — never silently dropped. Requires the
`Workflow` tool; where it's unavailable, the command says so and offers `/review`.
```

- [ ] **Step 3: README — update the Roadmap block**

Replace the `v0.4` roadmap line:

```markdown
- v0.4 — **`/workflow-review`**: planner-driven multi-agent review panel (fan-out + adversarial verification of every finding)
- v0.5 — tighter Graphify integration: review and learning files as typed graph nodes
```

(Previously `v0.4` was the Graphify-typed-nodes line; it moves to `v0.5`.)

- [ ] **Step 4: CLAUDE.md — add a project note**

Add this block after the `review-gate hook (v0.3.1)` section:

```markdown
## /workflow-review (v0.4.0)

Heavy multi-agent counterpart to `/review`. Command (`commands/workflow-review.md`)
scopes the diff and launches `workflows/workflow-review.js` via the **Workflow
tool**. Script phases: plan → review fan-out → adversarial verify (3 skeptics on
blocker/concern) → dedup (pure JS) → synthesize → one canonical `reviews/` file
(same schema + `commit_hash` as `/review`, so the review-gate + graphify keep
working).

- Reviewers read the four principles from `principlesPath` (passed in `args` as
  `${CLAUDE_PLUGIN_ROOT}/agents/karpathy-reviewer.md`) — SSOT, works in any
  consuming project, not just this repo.
- The script uses top-level `await`/`return`, legal only inside the Workflow
  runtime — `node --check` is NOT a valid syntax gate (it errors on the top-level
  return). The first `/workflow-review` launch is the syntax/runtime gate.
- After editing any plugin file: bump `plugin.json` version first (cache is
  version-gated), then `claude plugin update` + restart.
```

- [ ] **Step 5: COMMIT_PLAN.md — add a phase pointer**

Append at the end of `COMMIT_PLAN.md`:

```markdown
## Phase L — v0.4.0 /workflow-review (multi-agent review panel)

Planner-driven review panel. Full spec: `PRD-workflow-review.md`. Task-by-task
build: `PLAN-workflow-review.md`. Ships `workflows/workflow-review.js` +
`commands/workflow-review.md`, registers the command, bumps to v0.4.0. DoD =
live dogfood: a real multi-file diff yields a schema-valid `reviews/*.md` stamped
with HEAD, `_index.md` updated, summary printed, and a planted weak finding
visibly dropped by the adversarial pass.
```

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md COMMIT_PLAN.md
git commit -F - <<'EOF'
docs(workflow-review): README section + table + roadmap, CLAUDE.md note, COMMIT_PLAN phase L

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Task 5: Install the new version (manual checkpoint)

**No files.** This refreshes the local plugin cache so `/workflow-review` exists as a command. The cache is version-gated; the v0.4.0 bump from Task 3 is what makes the update re-pull.

- [ ] **Step 1: Update the plugin from the local marketplace**

Run: `claude plugin update boris-karpathy-loop@boris-karpathy-loop`
Expected: it reports an update to `0.4.0`. If it reports "already up to date" at 0.3.2, force-refresh: `claude plugin uninstall boris-karpathy-loop@boris-karpathy-loop` then `claude plugin install boris-karpathy-loop@boris-karpathy-loop`.

- [ ] **Step 2: Restart Claude Code**

Plugin content (commands) loads at session start — you must restart for `/workflow-review` to appear. **This ends the current session; Task 6 runs in the new one.** (Subagent-driven execution cannot perform this restart — hand back to the user here.)

- [ ] **Step 3: Confirm the command is registered**

Run: `claude plugin details boris-karpathy-loop@boris-karpathy-loop`
Expected: the command list includes `workflow-review`. (`/hooks` and `/plugin` are unavailable in this environment — use `claude plugin details`.)

---

## Task 6: Live dogfood — the real acceptance test

**No production files.** This is the verification gate for the whole feature. It builds a tiny known diff (with a deliberately weak finding) on a scratch branch, runs the panel, and checks the spec's acceptance criteria. Run this in the repo itself.

- [ ] **Step 1: Create a scratch diff with one real concern and one weak/non-issue**

```bash
git checkout -b scratch/workflow-review-dogfood
```
Create `scratch_demo.py` with content that gives the panel something real to find AND something a skeptic should refute:

```python
import json

def load_items(path):
    # Real CONCERN (Principle 1): silent empty-on-error fallback poisons callers.
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []

def total(items):
    # Intentionally fine — bait for a weak/hallucinated finding to be refuted.
    return sum(i.get("amount", 0) for i in items)
```

```bash
git add scratch_demo.py && git commit -m "test: scratch diff for workflow-review dogfood" \
  && git rev-parse HEAD
```
Note the HEAD sha — the review must stamp this exact `commit_hash`.

- [ ] **Step 2: Run the panel**

In Claude Code: `/workflow-review HEAD~1..HEAD`
Watch `/workflows` for live progress (plan → review → verify → synthesize).

- [ ] **Step 3: Verify the acceptance criteria**

Expected, all true:
1. A new `reviews/<today>-<slug>.md` exists; its `commit_hash` equals the sha from Step 1; all frontmatter fields present; `review_method` names the strategy + shard count.
2. `reviews/_index.md` gained the one-line entry.
3. The inline summary printed (blocker/concern/nit counts + strategy).
4. The `try/except: return []` concern (Principle 1) appears as a CONCERN (or BLOCKER) in the artifact.
5. The verify phase logged at least one `DROP ... refuted` line (the weak/non-issue finding was refuted) — visible, not silent.

Check the stamp matches:
```bash
git rev-parse HEAD            # from the scratch commit
# compare with the commit_hash line in the new reviews/ file
```

- [ ] **Step 4: Confirm `/review` still works (regression)**

Run `/review` on the same scratch diff. Expected: the single-agent path still produces its own `reviews/` file as before — unchanged behaviour.

- [ ] **Step 5: Tear down the scratch branch**

```bash
git checkout feat/workflow-review
git branch -D scratch/workflow-review-dogfood
```
Keep the produced `reviews/` dogfood file on `feat/workflow-review` as evidence (cherry-pick or recreate it on this branch), mirroring how the review-gate was "Live-proven". Commit it:

```bash
git add reviews/
git commit -F - <<'EOF'
test(workflow-review): live dogfood evidence — panel fires, weak finding dropped

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

- [ ] **Step 6: Update the PRD status**

Flip the PRD frontmatter `status: draft` → `status: shipped` and commit:

```bash
git add PRD-workflow-review.md
git commit -m "docs(workflow-review): mark PRD shipped — dogfood passed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** planner-matrix strategy (Task 1 planner) ✓; reads principles SSOT via `principlesPath` (Task 1 review stage + Task 2 args) ✓; adversarial verify 3-skeptics blocker/concern only (Task 1 verify) ✓; pure-JS dedup (Task 1) ✓; canonical commit_hash-stamped output + `_index.md` + summary (Task 1 synth) ✓; cost guardrails (shard cap 8 in planner prompt, nits unverified, budget-aware skeptics, caps recorded in `review_method`) ✓; coexists with `/review` (Task 6 Step 4 regression) ✓; version bump + manifest + validate (Task 3) ✓; README/CLAUDE/COMMIT_PLAN (Task 4) ✓; open risks (`${CLAUDE_PLUGIN_ROOT}` expansion + Workflow availability + cwd Read/Write) all surface at Task 5/6 with fallbacks stated ✓; acceptance = live dogfood with planted finding (Task 6) ✓.
- **Placeholder scan:** the `<feature-slug>` / `<today>` / `<path>` tokens are runtime template fields the synthesizer fills — intentional, not unfilled plan gaps. No TBD/TODO.
- **Type/name consistency:** `dedupeFindings`/`tallySeverity` defined and called with matching names; schema field names (`principle`, `severity`, `file`, `line`, `title`, `why`, `suggested_resolution`, `refuted`, `reason`, `strategy`, `shards`, `principles`, `files`, `why`, `caps_applied`) are identical between schema definitions and their use sites; `args` keys (`today`, `commitHash`, `range`, `scopeFiles`, `mustReview`, `reviewsDir`, `principlesPath`) match between the command's args object (Task 2) and the script's reads (Task 1).
