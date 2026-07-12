---
date: 2026-07-11
feature: workflow-review
commit_hash: e5fd7b230cfae83b564f3c414dc5d44c0e2f14dd
files_touched:
  - .claude-plugin/plugin.json
  - CLAUDE.md
  - COMMIT_PLAN.md
  - PLAN-workflow-review.md
  - PRD-workflow-review.md
  - README.md
  - commands/workflow-review.md
  - workflows/workflow-review.js
severity_summary:
  blocker: 0
  concern: 4
  nit: 4
status: resolved
verification_needed:
  - First live `/workflow-review` launch (script uses top-level await/return, legal only in the Workflow runtime — `node --check` is NOT a valid syntax gate)
  - Confirm behavior when a reviewer or skeptic agent errors/returns malformed output: does the artifact currently mislabel a failed shard as "clean" / a failed skeptic vote as "upheld"?
  - Confirm `commands/workflow-review.md`'s `date +%F` step actually runs via the Bash/Git-Bash tool (not PowerShell) in practice
review_method: "workflow-review (by-file, 4 shards, caps: Grouped 6 low-logic files into 2 buckets (config+user-docs, planning-docs) so the 8 changed files map to 4 meaningful shards; the two files carrying actual executable behavior (workflow-review.js, workflow-review.md) each get a dedicated shard.)"
---

# Review: /workflow-review multi-agent review panel

## Context
This change adds `/workflow-review`, a heavier multi-agent counterpart to the existing `/review` command. It ships a new command (`commands/workflow-review.md`) that scopes the diff and a new orchestration script (`workflows/workflow-review.js`) that runs a planner → reviewer fan-out → adversarial skeptic verification → dedup → synthesis pipeline via the Workflow tool, producing one canonical `reviews/` artifact with the same schema as `/review`. Supporting docs (README, COMMIT_PLAN, PLAN/PRD, CLAUDE.md) and the plugin manifest (version bump to 0.4.0) were updated alongside it.

## Findings

### [CONCERN] Verification passes when all skeptics error
- **Principle:** 1
- **Where:** workflows/workflow-review.js:169
- **Why it matters:** `refutes` is counted only over truthy votes (`votes.filter(Boolean)`) while the survival threshold uses the requested skeptic count. If every skeptic agent errors, `votes` is empty, `refutes=0`, and `refutes < ceil(skeptics/2)` is true, so the finding "survives" — and is then labeled `${skeptics - refutes}/${skeptics} upheld` (e.g. "3/3 upheld") even though zero verifications actually ran. The panel's core adversarial-verify guarantee silently degrades to a rubber stamp on agent failure, and the artifact asserts a verification that never happened.
- **Suggested resolution:** Distinguish "skeptic errored" from "skeptic voted not-refuted." Compute the denominator from actual returned votes, treat missing votes as inconclusive (fail-closed or re-run) rather than implicit upholds, and make the "upheld" label reflect real vote counts.

### [CONCERN] Errored reviewer shard indistinguishable from clean
- **Principle:** 1
- **Where:** workflows/workflow-review.js:150
- **Why it matters:** A reviewer agent that fails or returns malformed output hits `if (!review || !review.findings) return { shardIndex: i, findings: [] }`, byte-identical to a shard that genuinely found nothing. Combined with `reviewed.filter(Boolean)` at line 179 (which silently drops null pipeline results), a whole slice of the diff can go unreviewed while the synthesized canonical review still reports the change as clean. This is exactly the empty-on-error anti-pattern already codified in this project's own review principles.
- **Suggested resolution:** Surface reviewer/shard failures explicitly (e.g. carry an error marker into synthesis and add it to `verification_needed`, or fail the run) so a crashed reviewer never masquerades as a clean lens.

### [CONCERN] Failed reviewer shard reads as clean (plan doc)
- **Principle:** 1
- **Where:** PLAN-workflow-review.md:187
- **Why it matters:** The plan itself specifies the pipeline review stage returning `{findings: []}` on a null/failed reviewer, with dedup doing `reviewed.filter(Boolean).flatMap(...)`. This documents (and thus locks in) the same failed-shard-reads-as-clean defect described above at the design level, not just in the implementation — meaning the anti-pattern was baked into the spec, not merely an accidental slip in the code.
- **Suggested resolution:** Separate "reviewer errored/absent" from "reviewed, zero findings" in the plan's data model. Record failed shards in the artifact (e.g. an unreviewed-lenses note) instead of collapsing them to an empty findings set.

### [CONCERN] Budget-degraded skeptics silently weaken drop gate
- **Principle:** 1
- **Where:** PLAN-workflow-review.md:194
- **Why it matters:** Under a tight token budget skeptics drop from 3 to 1, and `survived = refutes < ceil(skeptics/2)` becomes "refutes < 1" — so a single skeptic that defaults to refuted=true on uncertainty kills a real BLOCKER/CONCERN. The PRD promises everything capped is visible in the artifact, but this per-finding degradation is only logged, not recorded in `review_method`, so "majority refutes = drop" silently degrades to "one uncertain skeptic drops it" with no trace in the output.
- **Suggested resolution:** Record the actual skeptic count per finding in the artifact when it was reduced, so a finding killed under a degraded gate is visibly distinguishable from one refuted by a real majority.

### [NIT] Magic 80000 budget threshold unexplained
- **Principle:** 1
- **Where:** workflows/workflow-review.js:157
- **Why it matters:** `budget.remaining() < 80000` silently switches verification from 3 skeptics to 1, materially changing review rigor, but the number is an unnamed literal with no rationale for why 80000 tokens is the cutoff.
- **Suggested resolution:** Extract to a named constant with a one-line comment on how it was chosen, or make it a tunable arg alongside the other args.

### [NIT] UNKNOWN commit_hash default breaks contract quietly
- **Principle:** 1
- **Where:** workflows/workflow-review.js:15
- **Why it matters:** `commitHash` defaults to `'UNKNOWN'` (and `today` to `'unknown-date'`) when args are missing. Since the artifact's `commit_hash` is the load-bearing link for the review-gate and graphify, a run with missing args writes a schema-valid but useless review instead of failing loudly.
- **Suggested resolution:** Treat a missing commitHash/today as an error (abort like the no-plan guard) rather than papering over it with a placeholder that silently corrupts the review-gate/graphify linkage.

### [NIT] `date +%F` assumes POSIX shell
- **Principle:** 1
- **Where:** commands/workflow-review.md:20
- **Why it matters:** In a Windows/PowerShell-primary repo (documented in this project's CLAUDE.md), `date +%F` errors or returns a wrong string under PowerShell; that value becomes the review artifact's filename and frontmatter date, so a silent mislabel is possible depending on which shell Claude picks.
- **Suggested resolution:** Either note that this must run under the Bash/Git-Bash tool, or give a shell-agnostic date instruction so the artifact date can't be silently wrong.

### [NIT] Unexplained hardcoded 80000 token threshold (plan doc)
- **Principle:** 1
- **Where:** PLAN-workflow-review.md:194
- **Why it matters:** `budget.remaining() < 80000` gates the 3-to-1 skeptic reduction with a bare magic number and no rationale for why 80000. It changes observable behavior (verification depth) and is neither a named constant nor documented, mirroring the same gap in the implementation.
- **Suggested resolution:** Lift 80000 to a named constant with a one-line rationale, or note in the plan why that threshold was chosen.

## What was done well
The pipeline design is coherent end-to-end: planner-driven sharding, adversarial verification with a majority-refute drop gate, pure-JS dedup, and a single canonical artifact reusing the existing `/review` schema (so review-gate and graphify integrations keep working unmodified) is a sound architecture for a heavier review tool. Budget-awareness (degrading skeptic count under token pressure rather than failing outright) is a reasonable design instinct, even though its failure-visibility needs work. Documentation (README, COMMIT_PLAN, PRD/PLAN) was updated in the same change rather than left to drift.

## Resolution (2026-07-11, in-session)

This review is itself the green dogfood of `/workflow-review` (PLAN Task 6): the panel
was run on its own branch diff and caught the empty-on-error anti-pattern in its own
code — the exact pattern its principle P1 exists to enforce. All findings addressed in
the same session, on top of `e5fd7b2`:

- **C1** (`js` verify tally): now judges over the skeptics that actually returned a vote;
  zero returns ⇒ finding kept but labeled `unverified`, never a phantom "3/3 upheld".
- **C2** (`js` reviewer guard): a failed/malformed reviewer returns `{failed:true, lens}`;
  failed + null-dropped shards are collected and forced into `verification_needed`, so a
  crashed shard can no longer read as "clean".
- **C3 / C4** (plan-doc mirrors): post-dogfood correction note added to
  `PLAN-workflow-review.md`; the degraded skeptic count is now visible per-finding in the
  `verified` field.
  **Correction (2026-07-12):** the self-review of this very fix commit
  (`reviews/2026-07-12-workflow-review-verify-gate.md`) caught that the C1 fix here was
  incomplete and this claim was WRONG: judging survival over `returned.length` let a
  *partial* skeptic outage (e.g. 2 of 3 errored) collapse the majority gate into a
  single-vote veto — no token budget involved. Fixed in the follow-up: survival is judged
  against a majority of the *requested* panel, so missing votes are never implicit refutes
  and a degraded drop is again only possible under the intentional budget reduction.
- **Nits**: `80000` lifted to `LOW_BUDGET_TOKENS` + `SKEPTICS_FULL/REDUCED` with rationale;
  `UNKNOWN`/`unknown-date` defaults replaced by fail-loud on missing required args;
  `date +%F` documented as Bash-only in the command.

**Verification caveat:** the C1/C2 fixes are verified by inspection, not by a run — the
error-paths (reviewer crash, all-skeptics-error) fired 0× across both dogfood runs, so a
third full-panel run would not exercise them. A stdlib unit test on the tally/`filter`
math is the cheaper real gate if hard proof is wanted.
