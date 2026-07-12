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
// The runtime may hand args through as a JSON string; normalise to an object so a
// launch never silently falls back to placeholder values (which would emit a
// plausible-but-wrong artifact named unknown-date / commit UNKNOWN).
const a = typeof args === 'string' ? JSON.parse(args) : (args || {})

// Required args: fail loudly rather than stub. today/commitHash stamp the artifact;
// principlesPath is where reviewers read the four principles (no repo-local default,
// so the SSOT stays portable to any consuming project).
const required = ['today', 'commitHash', 'principlesPath'].filter((k) => !a[k])
if (required.length) {
  log(`Missing required args: ${required.join(', ')} - aborting before any agent runs.`)
  return {
    error: 'bad-args',
    summary: `workflow-review: missing required args: ${required.join(', ')}. Launch via /workflow-review, which supplies them.`,
  }
}
const today = a.today
const commitHash = a.commitHash
const principlesPath = a.principlesPath

// Genuinely-optional args keep their defaults.
const range = a.range || null            // null => uncommitted (git diff HEAD)
const scopeFiles = a.scopeFiles || null  // null => all changed files
const mustReview = a.mustReview || []
const reviewsDir = a.reviewsDir || 'reviews'

// ---- per-phase model + reasoning-effort tuning ----
// Review + verify are the quality-critical stages: pinned to opus/high so the
// review never silently degrades if the session runs on a lighter model. The
// synthesizer only assembles already-verified+deduped findings into markdown from
// a fixed template, so it runs lighter (sonnet/medium) without touching review
// quality. The planner picks the shard strategy: opus, but effort need not max out.
const TUNING = {
  plan: { model: 'opus', effort: 'high' },
  review: { model: 'opus', effort: 'high' },
  verify: { model: 'opus', effort: 'high' },
  synthesize: { model: 'sonnet', effort: 'medium' },
}

// ---- verification tuning ----
// Full adversarial panel = 3 skeptics per BLOCKER/CONCERN (majority-refute drops it).
// Under token pressure we degrade to a single skeptic to finish the run rather than
// abort; the per-finding `verified` label records the ACTUAL count so a finding
// judged under the degraded gate is visibly distinct from a full-panel verdict.
// 80000 ~= headroom for one more full shard (planner + reviewer + 3 skeptics + synth).
const SKEPTICS_FULL = 3
const SKEPTICS_REDUCED = 1
const LOW_BUDGET_TOKENS = 80000

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

// ===== PURE-BEGIN =====
// Pure, dependency-free helpers (no Workflow globals). tests/test_workflow_review.js
// slices the source between the PURE-BEGIN / PURE-END fences and evals it, so it can
// unit-test this logic without launching the panel. Keep the fence markers exact and
// keep everything between them free of agent()/parallel()/log()/args/budget.
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

// Verdict for one finding given the raw skeptic votes (may contain nulls for errored
// skeptics) and the count that was REQUESTED. Refutes are counted only over votes that
// actually returned, but survival is judged against a majority of the requested panel -
// so a partial skeptic outage can never collapse the gate into a single-vote veto, and
// missing votes are inconclusive rather than implicit refutes. Zero returns => keep the
// finding but never claim a verdict. Returns { survived, unverified, refutes, returned,
// errored, label }. Assumes an odd panel size (the only callers pass SKEPTICS_FULL=3 or
// SKEPTICS_REDUCED=1); an even size would make ceil(n/2) a bare-minority threshold.
function verifyVerdict(votes, skeptics) {
  const returned = votes.filter(Boolean)
  const errored = skeptics - returned.length
  const skepticWord = (n) => `skeptic${n === 1 ? '' : 's'}`
  if (returned.length === 0) {
    return { survived: true, unverified: true, refutes: 0, returned: 0, errored, label: `unverified (all ${skeptics} ${skepticWord(skeptics)} errored)` }
  }
  const refutes = returned.filter((v) => v.refuted).length
  const survived = refutes < Math.ceil(skeptics / 2)
  const label = errored
    ? `${returned.length - refutes}/${returned.length} upheld (${errored}/${skeptics} skeptics errored)`
    : `${returned.length - refutes}/${returned.length} upheld`
  return { survived, unverified: false, refutes, returned: returned.length, errored, label }
}

// Shards that never produced a real review: explicit { failed:true } markers AND null
// entries (a pipeline stage that threw is dropped to null). Returns human-readable labels.
function collectFailedShards(reviewed) {
  return reviewed.reduce((acc, r, idx) => {
    if (r === null) acc.push(`shard${idx + 1} (pipeline error)`)
    else if (r && r.failed) acc.push(`shard${idx + 1}: ${r.lens}`)
    return acc
  }, [])
}
// ===== PURE-END =====

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
  { phase: 'Plan', schema: PLAN_SCHEMA, ...TUNING.plan }
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
      { label: `review:shard${i + 1}`, phase: 'Review', schema: FINDINGS_SCHEMA, ...TUNING.review }
    )
  },
  async (review, shard, i) => {
    // C2: a failed/malformed reviewer is NOT a clean lens. An agent that dies
    // returns null; a schema-violating one lacks a findings array. Either way,
    // mark the shard failed so synthesis surfaces the UNREVIEWED slice instead of
    // the diff silently reading as clean (the empty-on-error anti-pattern this
    // panel exists to catch).
    const lens = (shard.files && shard.files[0] !== '*' ? shard.files.join(', ') : 'whole diff') +
      ` [P${(shard.principles || []).join('/')}]`
    if (!review || !Array.isArray(review.findings)) {
      log(`REVIEWER FAILED shard${i + 1} (${lens}) - lens left UNREVIEWED`)
      return { shardIndex: i, findings: [], failed: true, lens }
    }
    const kept = []
    for (const f of review.findings) {
      if (f.severity === 'NIT') {
        kept.push({ ...f, verified: 'nit-unverified' })
        continue
      }
      const skeptics = budget.total && budget.remaining() < LOW_BUDGET_TOKENS ? SKEPTICS_REDUCED : SKEPTICS_FULL
      const votes = await parallel(
        Array.from({ length: skeptics }, (_v, k) => () =>
          agent(
            `You are skeptic #${k + 1} trying to REFUTE a code-review finding. Default to refuted=true if uncertain.
Run \`${diffCmd}\` to inspect the actual change.
Finding - principle ${f.principle}, ${f.severity}: "${f.title}" at ${f.file}:${f.line}. Why claimed: ${f.why}.
Is this finding real and material to THIS diff, or is it wrong / overstated / not actually present? Return refuted (boolean) + a one-line reason.`,
            { label: `verify:s${i + 1}:${f.file}`, phase: 'Verify', schema: VERDICT_SCHEMA, ...TUNING.verify }
          )
        )
      )
      // Verdict via the pure helper (PURE block above; unit-tested in
      // tests/test_workflow_review.js). unverified => keep but claim no verdict.
      const v = verifyVerdict(votes, skeptics)
      const decision = v.unverified ? 'UNVERIFIED' : v.survived ? 'KEEP' : 'DROP'
      log(`${decision} [${f.severity}] ${f.title} (${f.file}:${f.line}) - ${v.refutes}/${skeptics} refuted${v.errored ? `, ${v.errored} errored` : ''}`)
      if (v.survived) kept.push({ ...f, verified: v.label })
    }
    return { shardIndex: i, findings: kept, failed: false }
  }
)

// ---- Phase 4: Dedup (pure JS, no agent) ----
// C2: collect shards that never produced a real review - explicit `failed:true`
// markers AND null entries (a stage that threw is dropped to null by pipeline()).
// These are unreviewed slices, not clean ones, and must reach the artifact.
const failedShards = collectFailedShards(reviewed)
if (failedShards.length) log(`WARNING: ${failedShards.length}/${reviewed.length} shard(s) left UNREVIEWED: ${failedShards.join('; ')}`)

const allFindings = reviewed.filter(Boolean).flatMap((r) => r.findings)
const deduped = dedupeFindings(allFindings)
log(`${allFindings.length} findings survived verify -> ${deduped.length} after dedup`)

// ---- Phase 5: Synthesize ----
phase('Synthesize')
const counts = tallySeverity(deduped)
const failedNote = failedShards.length
  ? `\n\nCOVERAGE WARNING - ${failedShards.length} reviewer shard(s) FAILED and left part of the diff UNREVIEWED: ${failedShards.join('; ')}. You MUST add a verification_needed bullet that names these unreviewed shards, and append " [WARNING: ${failedShards.length} shard(s) unreviewed]" to the review_method string, so a low finding count is never mistaken for full coverage.`
  : ''
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
- **Verification:** <this finding's \`verified\` value VERBATIM from the JSON below — e.g. "3/3 upheld", "1/1 upheld (2/3 skeptics errored)", "unverified (all 3 skeptics errored)", or "nit-unverified">

## What was done well
<brief, honest>

The findings to write (already adversarially verified + deduped), as JSON. Each finding
carries a \`verified\` field — copy it VERBATIM into that finding's **Verification** line so a
degraded or unverified verdict stays visible in the artifact, not just in the run logs:
${JSON.stringify(deduped, null, 2)}${failedNote}

After writing the review file, append ONE line to \`${reviewsDir}/_index.md\` (create the file if missing), matching the existing one-line format:
- ${today} \`<feature-slug>\` - ${counts.blocker} blockers, ${counts.concern} concerns, ${counts.nit} nits ([link](./${today}-<feature-slug>.md))

Then return EXACTLY this summary text and nothing else:
workflow-review: ${reviewsDir}/${today}-<feature-slug>.md
  - ${counts.blocker} blockers
  - ${counts.concern} concerns
  - ${counts.nit} nits
  - strategy: ${plan.strategy} (${plan.shards.length} shards)
Open the file for full details.`,
  { phase: 'Synthesize', ...TUNING.synthesize }
)

return { summary, strategy: plan.strategy, shards: plan.shards.length, counts }
