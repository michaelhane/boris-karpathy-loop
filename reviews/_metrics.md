# Karpathy Loop — Dogfood Metrics

Phase D4 tracking. First measurement: 2026-05-30 (covers v0.2.0 → v0.2.3,
dogfood window 2026-05-06 → 2026-05-30).

## Per-review ledger

| Date       | Feature                     | Commit   | B | C | N | Total | Status   |
|------------|-----------------------------|----------|---|---|---|-------|----------|
| 2026-05-07 | v0.2-setup-and-diagnose     | 9bc8ddd  | 0 | 4 | 4 | 8     | **open** |
| 2026-05-07 | v0.2.1-fixups               | 3720a5a  | 0 | 1 | 2 | 3     | resolved |
| 2026-05-30 | v0.2.2-uv-tool-install-fix  | 0a8a8aa  | 0 | 0 | 2 | 2     | **open** |
| 2026-05-30 | v0.2.3-hook-fix             | 587c7b7  | 0 | 1 | 3 | 4     | closed   |

## Aggregate (D4 spec fields)

- **Reviews run:** 4
- **findings_per_review (mean):** 4.25 (median 3.5, range 2–8)
- **Severity totals:** 0 blockers / 6 concerns / 11 nits = 17 findings
- **% closed within 7 days:** 25% (1 of 4) — see caveat below
- **Outstanding findings:** v0.2-setup (4 concerns + 4 nits), v0.2.2 (2 nits)

### Metric caveat — wall-clock vs. active-session

The 7-day window is distorted by a 23-day inter-session gap (2026-05-07 →
2026-05-30). v0.2.1 was closed in the *next working session*, not slowly. The
honest signal is not "closures are slow" — it is that **v0.2-setup was never
reconciled at all**, across three subsequent releases. For an intermittent
project, "closed before the next release tag" is a truer metric than calendar
days. By that measure: v0.2.1 ✓ (closed by v0.2.2), v0.2.3 ✓ (same commit),
v0.2-setup ✗ (open across v0.2.1/.2/.3), v0.2.2 ✗ (still open).

## Subjective: did review noise dominate signal?

**No.** 0 blockers across the whole window; 11 of 17 findings were nits. The
mean of 4.25 is inflated by v0.2-setup's 8 findings — but that was the initial
two-command release (large change), not a moderate edit. The moderate edits
(v0.2.2, v0.2.3) produced 2 and 4 findings — inside the dogfood band of "0–2
nits, ≤1 concern." The single highest-value event was the loop **catching its
own false-close**: v0.2.1 parked a finding in `verification_needed`, Phase F3
dispositioned it against an unrelated smoke test, and v0.2.2 proved it was a
real bug. The methodology earned its keep.

## Four-signal dogfood scorecard (from project memory `dogfood-v0.1`)

1. **/loop-bootstrap on empty project (≤4 lines):** ⚠️ NO DATA — never run in a
   project without `reviews/` + `graphify-out/`. Carry to next dogfood.
2. **/review strictness (S/N):** ✅ PASS — moderate edits within band; not too
   strict, not too lax (caught a real bug). No threshold change warranted.
3. **/tutor diagnose-first:** ⚠️ NO DATA — `/tutor` never invoked on a genuine
   gap. Carry to next dogfood.
4. **Review-file format:** ✅ PASS — severity tags render; `verification_needed`
   is concrete and actionable (it is what surfaced the v0.2.1→v0.2.2 bug).

### Signal #5 (discovered by running D4): status-lifecycle drift

The loop has **no reliable step that flips `status: open` → `closed` and syncs
`_index.md` when a finding's fix ships.** v0.2.2 performed this reconciliation
*manually* for the v0.2.1 review (and flagged the drift as its own nit), but
v0.2-setup — the oldest and largest review — slipped through and has read
`open` for 23 days while parts of it were already fixed. This is the mirror of
the false-close: a **false-open**. It erodes trust in the index as a source of
truth (loop-bootstrap reported "0 open findings" off `_index.md`; the
front-matter said otherwise).

## Decision (D4 "after two weeks")

1. **Roll out to Chef2 Gemini / OOTA?** → **Yes, but gated on v0.2.4.** The
   methodology is validated; do not propagate the status-drift weakness to new
   projects first.
2. **Adjust severity thresholds in `karpathy-reviewer.md`?** → **No.** S/N is
   healthy; 0 blockers, mostly nits, one real catch. Leave the rubric.
3. **Cut a version with adjustments?** → **Yes — v0.2.4**, scoped to:
   - **(a) Reconcile the two open reviews.** Triage v0.2-setup's 4 concerns
     (hypothesis at the time: auth-conflict / `GEMINI_API_KEY` validation /
     chunk-failure detection *might* be unaddressed — **superseded by the Update
     below: all four were already fixed in `130b720`**);
     flip v0.2.2 to `closed` with a "2 nits left as-is, defensible" note.
   - **(b) Encode a close-out step** so signal #5 cannot recur — a checklist or
     `/review-review` extension that flips `status` and edits `_index.md` when a
     fix lands, so the index is never ahead of the front-matter.

## Next dogfood window

Deliberately exercise the two no-data signals: run `/loop-bootstrap` in a fresh
empty project (verify ≤4 lines), and `/tutor` on a real knowledge gap (verify
diagnose-before-lecture). Re-measure this file after the next 3–4 reviews.

## Update (2026-05-30) — v0.2.4 acted on signal #5

The decision above was executed as **v0.2.4** (COMMIT_PLAN Phase I):
- Both open reviews reconciled — `v0.2-setup` (`open`→`resolved`, all findings
  attributed to `130b720`/`fe5ab5c`), `v0.2.2` (`open`→`closed`), `_index` synced.
- Root cause refined: the write-back mechanism already existed in
  `/review-review`; the gap was **no trigger** + `/loop-bootstrap` trusting
  `_index` prose over front-matter. Fix = detection in `/loop-bootstrap`
  (front-matter is source of truth; flag stale-open) + a documented three-layer
  lifecycle. No script built (YAGNI; revisit-trigger recorded).
- Threshold decision held: **no** change to `karpathy-reviewer.md` severity rubric.

## Update (2026-06-11) — dogfood window 2: the two NO-DATA signals

Method (per PRD 2026-06-11 in COMMIT_PLAN): signal #1 was measured in a
**fresh headless session** (`claude -p "/loop-bootstrap"`) with cwd set to a
throwaway empty dir (`mktemp -d` — no `reviews/`, no `graphify-out/`, no git).
Running it from this repo would not be representative: loop-bootstrap reads cwd.

- **Signal #1 — /loop-bootstrap on empty project (≤4 lines): ✅ PASS.**
  Output took the "When nothing exists" path: 3 non-empty lines (5 raw lines
  incl. blanks), within the ≤4 band. Content was correct: absence of
  `reviews/` + `graphify-out/` stated, seeding suggested (`/review` after
  meaningful changes, `graphify .` once), then handed control back ("Ready
  for today's task"). Measured 2026-06-11 on plugin v0.3.1.
- **Signal #3 — /tutor diagnose-first: ⚠️ still NO DATA.** Per the PRD
  decision this piggybacks on the first *genuine* leervraag — not a forced
  artificial one. None occurred yet; log the observation line here the moment
  it happens.

Scorecard after this window: #1 ✅ · #2 ✅ · #4 ✅ · #5 ✅ (closed by v0.2.4) ·
#3 ⚠️ pending a real tutoring occasion.
