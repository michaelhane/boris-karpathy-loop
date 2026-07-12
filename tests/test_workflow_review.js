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

const { dedupeFindings, tallySeverity, verifyVerdict, collectFailedShards } = new Function(
  block + '\nreturn { dedupeFindings, tallySeverity, verifyVerdict, collectFailedShards }'
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

console.log(`\nAll ${passed} tests passed.`)
