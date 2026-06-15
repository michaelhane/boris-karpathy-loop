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
