---
date: 2026-07-12
feature: workflow-review-verify-gate
commit_hash: 9455dcb2d08ab25ace8b1b495d8e59960cf11d72
files_touched:
  - .claude-plugin/plugin.json
  - PLAN-workflow-review.md
  - commands/workflow-review.md
  - reviews/2026-07-11-workflow-review.md
  - reviews/_index.md
  - workflows/workflow-review.js
severity_summary:
  blocker: 0
  concern: 2
  nit: 1
status: resolved
verification_needed:
  - "Confirm the C1 refute-tally treats a skipped/errored skeptic differently from a real refute when returned < requested skeptics (currently both collapse into the same `returned.length` denominator)."
  - "Run a stdlib/node unit test over the pure tally/filter and failedShards-reduce logic in workflow-review.js covering returned.length in {0,1,2,3}."
  - "On the next /workflow-review launch, confirm the sonnet/medium synthesizer still emits a schema-correct reviews/ artifact and a well-formed reviews/_index.md line."
review_method: "workflow-review (by-principle, 4 shards)"
---

# Review: Dogfood fixes to workflow-review's verify/synthesize gate

## Context
This change is the dogfood-driven follow-up to `/workflow-review` (v0.4.0/v0.4.1): it hardens argument parsing, changes empty-result handling from silent-pass to empty-on-error, and reworks the adversarial verify stage in `workflows/workflow-review.js` (the refute tally and `failedShards` collection), plus tunes the synthesize step to a lighter model. The prior review (`reviews/2026-07-11-workflow-review.md`) had already flagged the original empty-on-error anti-pattern; this commit is meant to close that loop, but the fix itself introduces a related silent-degradation risk in the verify gate.

## Findings

### [CONCERN] Partial skeptic errors silently shrink the drop gate
- **Principle:** 1
- **Where:** workflows/workflow-review.js:231
- **Why it matters:** The tally judges over `returned = votes.filter(Boolean)`, so `survived = refutes < ceil(returned.length/2)`. If 3 skeptics are requested but 2 error out and only 1 returns, `refutes=1` against `ceil(1/2)=1` drops the finding on a single vote — silently collapsing the intended 2-of-3 majority gate into a 1-vote veto whenever skeptics error, with no trace of the drop left in the artifact. This directly contradicts the resolution note in `reviews/2026-07-11-workflow-review.md:99`, which claims the degraded gate is "only reachable under an explicit token budget" — partial agent errors reach it with no budget involved. The "N/M upheld" labels also conflate "intentionally reduced to 1 skeptic" with "requested 3, 2 errored."
- **Suggested resolution:** Track requested-vs-returned skeptic counts separately; when returned < requested, either fail-closed / re-run the missing skeptics, or explicitly record the degraded panel (and any finding dropped under it) in `verification_needed` / `review_method` so a partial-error drop is visibly distinct from a genuine majority refute. Disambiguate the "...upheld" label accordingly.

### [CONCERN] C1/C2 verify-integrity fixes ship untested
- **Principle:** 4
- **Where:** workflows/workflow-review.js:224
- **Why it matters:** This commit rewrites the panel's core verification logic — the refute tally at lines 224-233 and the `failedShards` collection at lines 243-248 — which is the exact guarantee the panel exists to provide, yet no test exercises it. Only `tests/test_review_gate.py` exists in the repo; nothing covers `workflow-review.js`. The new branches (all-skeptics-errored, reviewer `failed:true`, null-shard collection) fire zero times on a clean run, so no ordinary run can validate them. The resolution note itself concedes the fixes are "verified by inspection, not by a run" and names "a stdlib unit test on the tally/filter math" as the cheaper real gate — then omits adding it.
- **Suggested resolution:** Add a stdlib/node unit test over the pure branch logic: refute/survived math for `returned.length` in {0,1,2,3}, and the `failedShards` reduce over mixed null/failed/clean entries. These are pure functions and trivially testable without launching the full panel.

### [NIT] Synthesizer model downgrade unverified
- **Principle:** 4
- **Where:** workflows/workflow-review.js:50
- **Why it matters:** The tuning change routes the synthesize phase — the step that writes the `reviews/` artifact and appends the `_index.md` line — to sonnet/medium instead of opus. This changes the observable reliability of the file-writing/schema-compliance step, but nothing checks that the lighter model still emits a schema-correct artifact and a well-formed index entry. Success is asserted by prose ("a fixed template, so it runs lighter without touching review quality"), not demonstrated by a run.
- **Suggested resolution:** On the next `/workflow-review` launch, confirm the sonnet/medium synthesizer produces a frontmatter-valid artifact and a correctly-formatted `_index.md` line; if unverified, keep synthesize on the prior model until confirmed.

## What was done well
This commit closes a real loop: it responds directly to the prior review's finding on empty-on-error handling and args robustness, and the resolution notes in `reviews/2026-07-11-workflow-review.md` show honest self-assessment (explicitly naming "verified by inspection, not by a run" rather than claiming false confidence). The per-step model tuning is a reasonable cost optimization for a fixed-template step, just currently unverified.

## Resolution (2026-07-12, in-session)

All three findings addressed on top of `9455dcb`, and this time verified by a real test, not inspection:

- **C1** (verify gate collapses under partial skeptic outage): the tally now judges survival against a majority of the *requested* panel (`refutes < Math.ceil(skeptics / 2)`), so errored skeptics are inconclusive, never implicit refutes — the single-vote veto is gone. The verify/tally and `failedShards` logic were refactored into pure functions (`verifyVerdict`, `collectFailedShards`) inside a fenced `PURE` block.
- **C2** (fixes shipped untested): added `tests/test_workflow_review.js` (stdlib node) that slices the `PURE` block from the source and evals it, so it exercises the actual shipped logic — 15 cases incl. the C1 guard (`1 refute + 2 errored → SURVIVES`). An independent opus review ran a **mutation check**: reverting the denominator to `returned.length` makes the C1-guard test fail, and `<`→`<=` makes the majority test fail — the test is a real gate, not vacuous.
- **NIT** (synth downgrade): the 2026-07-11 run already emitted a schema-correct artifact under sonnet/medium; left as-is.
- **Extra (found by the opus verification):** the `verified` label was stamped on each finding but never rendered by the synthesizer — it lived only in run logs. Fixed: the artifact's finding template now carries a **Verification** line populated verbatim from each finding's `verified` value, so a degraded/unverified verdict is visible in the persisted review. Also fixed the `all 1 skeptic errored` pluralization.

**Runtime note:** the outside-`PURE` parts (callback wiring, synth template) are not covered by `node --check` (top-level await/return); the next real `/workflow-review` launch remains their runtime gate. Shipped as plugin v0.4.2.
