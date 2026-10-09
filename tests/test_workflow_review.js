'use strict'
// Unit tests for the PURE helpers in workflows/workflow-review.js.
//
// The script is a Workflow-runtime module (top-level await/return, globals like
// agent()/parallel()/budget) and cannot be require()d. Instead we read the source,
// slice the fenced // ===== PURE-BEGIN/END ===== block (which is dependency-free) and
// eval it - so these tests exercise the ACTUAL shipped logic, with no duplication.
//
// Run: node tests/test_workflow_review.js   (stdlib only, no deps)

const fs = require('fs')
const path = require('path')
const assert = require('assert')

const SCRIPT = path.join(__dirname, '..', 'workflows', 'workflow-review.js')
const src = fs.readFileSync(SCRIPT, 'utf8')

const BEGIN = '// ===== PURE-BEGIN ====='
const END = '// ===== PURE-END ====='
const b = src.indexOf(BEGIN)
const e = src.indexOf(END)
assert(b !== -1 && e !== -1 && e > b, 'PURE-BEGIN / PURE-END fences must be present and ordered')
const block = src.slice(b, e)

// Fence guard: the pure block must not reference Workflow-only globals, else eval-ing it
// in isolation (and, more importantly, the "pure" claim) is a lie. Scan code only -
// strip comments first so the guard doesn't trip over its own documentation.
const codeOnly = block.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')
for (const forbidden of ['agent(', 'parallel(', 'pipeline(', 'log(', 'phase(', 'budget.', 'args.']) {
  assert(!codeOnly.includes(forbidden), `PURE block must not use Workflow global: ${forbidden}`)
}

const { dedupeFindings, tallySeverity, verifyVerdict, collectFailedShards, buildSummary, gitDiffCmd, clampShards } = new Function(
  block + '\nreturn { dedupeFindings, tallySeverity, verifyVerdict, collectFailedShards, buildSummary, gitDiffCmd, clampShards }'
)()

let passed = 0
function check(name, fn) {
  fn()
  passed++
  console.log(`  ok - ${name}`)
}

// ---- helpers to build a raw votes array (length === skeptics, null = errored) ----
function votes({ refuted = 0, upheld = 0, errored = 0 }) {
  return [
    ...Array.from({ length: refuted }, () => ({ refuted: true, reason: 'r' })),
    ...Array.from({ length: upheld }, () => ({ refuted: false, reason: 'u' })),
    ...Array.from({ length: errored }, () => null),
  ]
}

console.log('verifyVerdict - full panel (skeptics=3):')

check('0 refutes -> survives, honest label', () => {
  const v = verifyVerdict(votes({ upheld: 3 }), 3)
  assert.strictEqual(v.survived, true)
  assert.strictEqual(v.unverified, false)
  assert.strictEqual(v.errored, 0)
  assert.strictEqual(v.label, '3/3 upheld')
})

check('1 refute -> survives (minority)', () => {
  const v = verifyVerdict(votes({ refuted: 1, upheld: 2 }), 3)
  assert.strictEqual(v.survived, true)
  assert.strictEqual(v.label, '2/3 upheld')
})

check('2 refutes -> drops (majority of 3)', () => {
  const v = verifyVerdict(votes({ refuted: 2, upheld: 1 }), 3)
  assert.strictEqual(v.survived, false)
})

check('3 refutes -> drops', () => {
  const v = verifyVerdict(votes({ refuted: 3 }), 3)
  assert.strictEqual(v.survived, false)
})

// The C1 regression guard: with the OLD `returned.length` denominator this case
// dropped on a single vote. It MUST survive - a partial outage is not a majority.
check('C1 GUARD: 1 refute + 2 errored -> SURVIVES (no single-vote veto)', () => {
  const v = verifyVerdict(votes({ refuted: 1, errored: 2 }), 3)
  assert.strictEqual(v.survived, true, 'partial skeptic outage must not collapse the majority gate')
  assert.strictEqual(v.errored, 2)
  assert.strictEqual(v.label, '0/1 upheld (2/3 skeptics errored)')
})

check('2 refutes + 1 errored -> drops (genuine majority of 3)', () => {
  const v = verifyVerdict(votes({ refuted: 2, errored: 1 }), 3)
  assert.strictEqual(v.survived, false)
  assert.strictEqual(v.errored, 1)
})

check('1 refute + 1 upheld + 1 errored -> survives, discloses outage', () => {
  const v = verifyVerdict(votes({ refuted: 1, upheld: 1, errored: 1 }), 3)
  assert.strictEqual(v.survived, true)
  assert.strictEqual(v.label, '1/2 upheld (1/3 skeptics errored)')
})

check('all errored -> unverified, kept, no verdict claimed', () => {
  const v = verifyVerdict(votes({ errored: 3 }), 3)
  assert.strictEqual(v.unverified, true)
  assert.strictEqual(v.survived, true)
  assert.strictEqual(v.label, 'unverified (all 3 skeptics errored)')
})

console.log('verifyVerdict - budget-reduced panel (skeptics=1):')

check('1 refute -> drops (intentional budget veto)', () => {
  const v = verifyVerdict(votes({ refuted: 1 }), 1)
  assert.strictEqual(v.survived, false)
})

check('1 uphold -> survives', () => {
  const v = verifyVerdict(votes({ upheld: 1 }), 1)
  assert.strictEqual(v.survived, true)
  assert.strictEqual(v.label, '1/1 upheld')
})

check('reduced + errored -> unverified', () => {
  const v = verifyVerdict(votes({ errored: 1 }), 1)
  assert.strictEqual(v.unverified, true)
  assert.strictEqual(v.label, 'unverified (all 1 skeptic errored)')
})

console.log('collectFailedShards:')

check('mixes null (pipeline error), failed marker, and clean shards', () => {
  const reviewed = [
    { shardIndex: 0, findings: [{}], failed: false },
    null,
    { shardIndex: 2, findings: [], failed: true, lens: 'workflows/x.js [P3]' },
    { shardIndex: 3, findings: [], failed: false },
  ]
  assert.deepStrictEqual(collectFailedShards(reviewed), [
    'shard2 (pipeline error)',
    'shard3: workflows/x.js [P3]',
  ])
})

check('all-clean -> empty', () => {
  const reviewed = [
    { failed: false, findings: [] },
    { failed: false, findings: [{}] },
  ]
  assert.deepStrictEqual(collectFailedShards(reviewed), [])
})

console.log('dedupeFindings / tallySeverity:')

check('dedupeFindings drops identical file|line|principle|title', () => {
  const f = { file: 'a.js', line: 5, principle: 1, title: 'X', severity: 'CONCERN' }
  const out = dedupeFindings([f, { ...f }, { ...f, line: 6 }])
  assert.strictEqual(out.length, 2)
})

check('tallySeverity counts by severity', () => {
  const c = tallySeverity([
    { severity: 'BLOCKER' }, { severity: 'CONCERN' }, { severity: 'CONCERN' }, { severity: 'NIT' },
  ])
  assert.deepStrictEqual(c, { blocker: 1, concern: 2, nit: 1 })
})

console.log('buildSummary:')

check('summary carries path, counts and strategy', () => {
  const s = buildSummary('reviews/2026-10-02-x.md', { blocker: 1, concern: 2, nit: 3 }, 'by-file', 4, 0)
  assert.strictEqual(s, [
    'workflow-review: reviews/2026-10-02-x.md',
    '  - 1 blockers',
    '  - 2 concerns',
    '  - 3 nits',
    '  - strategy: by-file (4 shards)',
    'Open the file for full details.',
  ].join('\n'))
})

check('summary warns about unreviewed shards', () => {
  const s = buildSummary('r.md', { blocker: 0, concern: 0, nit: 0 }, 'matrix', 8, 2)
  assert(s.includes('  - WARNING: 2 shard(s) unreviewed\nOpen the file'))
})

console.log('\ngitDiffCmd:')

check('no range, no scope -> git diff HEAD', () => {
  assert.strictEqual(gitDiffCmd('', null, null), 'git diff HEAD')
})

check('range + --name-only -> flag before range', () => {
  assert.strictEqual(gitDiffCmd('--name-only', 'HEAD~1..HEAD', null), 'git diff --name-only HEAD~1..HEAD')
})

check('scopeFiles -> root-anchored, single-quoted pathspec after --', () => {
  assert.strictEqual(
    gitDiffCmd('--numstat', 'HEAD~1..HEAD', ['a.js', 'b/c.md']),
    "git diff --numstat HEAD~1..HEAD -- ':(top)a.js' ':(top)b/c.md'"
  )
})

check('pathspec survives spaces, $ and quotes', () => {
  assert.strictEqual(
    gitDiffCmd('', null, ["my dir/$x `y`.md", "it's.js"]),
    "git diff HEAD -- ':(top)my dir/$x `y`.md' ':(top)it'\\''s.js'"
  )
})

check('empty scopeFiles array -> no pathspec', () => {
  assert.strictEqual(gitDiffCmd('', null, []), 'git diff HEAD')
})

console.log('\nclampShards:')

const shardList = (n) => Array.from({ length: n }, (_v, i) => ({ principles: [1], files: [`f${i + 1}.js`], why: `w${i + 1}` }))

check('12 shards -> 8 kept (first 8), caps_applied names the overshoot', () => {
  const out = clampShards({ strategy: 'by-file', shards: shardList(12) }, 8)
  assert.strictEqual(out.shards.length, 8)
  assert.deepStrictEqual(out.shards.map((s) => s.files[0]), ['f1.js', 'f2.js', 'f3.js', 'f4.js', 'f5.js', 'f6.js', 'f7.js', 'f8.js'])
  assert.strictEqual(out.caps_applied.length, 1)
  assert(/12/.test(out.caps_applied[0]) && /8/.test(out.caps_applied[0]), 'cap note must carry the planner count and the limit')
  // caps_applied lands inside a double-quoted YAML string in the artifact front-matter.
  assert(!out.caps_applied[0].includes('"'), 'cap note must not contain a double quote')
})

check('12 shards + planner caps -> planner caps kept, code cap appended', () => {
  const out = clampShards({ shards: shardList(12), caps_applied: ['grouped files'] }, 8)
  assert.strictEqual(out.shards.length, 8)
  assert.strictEqual(out.caps_applied.length, 2)
  assert.strictEqual(out.caps_applied[0], 'grouped files')
})

check('exactly 8 shards -> untouched, no cap note', () => {
  const out = clampShards({ shards: shardList(8), caps_applied: ['grouped files'] }, 8)
  assert.strictEqual(out.shards.length, 8)
  assert.deepStrictEqual(out.caps_applied, ['grouped files'])
})

check('4 shards, no planner caps -> untouched, empty caps_applied', () => {
  const out = clampShards({ shards: shardList(4) }, 8)
  assert.strictEqual(out.shards.length, 4)
  assert.deepStrictEqual(out.caps_applied, [])
})

check('clampShards does not mutate the planner result', () => {
  const plan = { shards: shardList(12), caps_applied: ['x'] }
  clampShards(plan, 8)
  assert.strictEqual(plan.shards.length, 12)
  assert.deepStrictEqual(plan.caps_applied, ['x'])
})

check('WIRING: the limit is 8 and the plan passes through clampShards', () => {
  assert(/const MAX_SHARDS = 8\b/.test(src), 'MAX_SHARDS must be the single named limit, set to 8')
  const outsidePure = src.slice(0, b) + src.slice(e)
  assert(/clampShards\(\s*planned\s*,\s*MAX_SHARDS\s*\)/.test(outsidePure), 'plan must be clamped with MAX_SHARDS before use')
  assert(outsidePure.includes('${MAX_SHARDS}'), 'planner prompt must take the limit from MAX_SHARDS, not a second literal')
})

console.log(`\nAll ${passed} tests passed.`)
