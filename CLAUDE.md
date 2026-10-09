## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)

## review-gate hook (v0.3.1)

This plugin ships a `PreToolUse` (Bash) + `Stop` review-gate (`hooks/`), opt-in per consuming project via `.claude/review-gate.json`. Plugin default = OFF (no config ⇒ silent).

- Verify it's loaded with `claude plugin details boris-karpathy-loop@boris-karpathy-loop` — **`/hooks` and `/plugin` are unavailable in this environment**, so don't rely on them.
- After changing **any** plugin file (`hooks/`, `agents/`, `commands/`, `skills/`, `.claude-plugin/*.json`): **bump `plugin.json` `version` first** — `claude plugin update` is version-gated against the local cache, so a same-version edit will NOT re-pull (the bump is the delivery mechanism, not ceremony). Then `claude plugin update boris-karpathy-loop@boris-karpathy-loop` and **restart Claude** (plugin content loads at session start). To force-refresh at the *same* version: `claude plugin uninstall …@…` + `install …@…`. Marketplace is a local Directory → no GitHub push needed for local use. (memory `plugin-cache-version-gated`)
- Tests: `python tests/test_review_gate.py` and `node tests/test_workflow_review.js` (both dependency-free). Full plan + DoD: COMMIT_PLAN Phase J (v0.3.0) + Phase K (v0.3.1).
- Both triggers (merge-gate `ask` + stop-nudge) are proven live; evidence in the COMMIT_PLAN DoD-close. `claude plugin details` showing "Agents (0)" is a harmless display quirk — the karpathy-reviewer launches fine.

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

## Control flow, bounds and state (read from code)

Where the review flow branches, what caps it, and where its state lives. Line numbers point to the code that reads each value; update them when the code moves.

**Conditional edges, review gate** (`hooks/review_gate.py`). Every guard falls through to silent, so a broken gate never blocks work. The gate speaks only when all of these hold:
- The command is a git merge/push (`:428-430`), `.claude/review-gate.json` is enabled with a non-empty `must_review` (`:437-443`), and the diff touches a `must_review` path (`:471`).
- No review in `reviews/` carries the tip's `commit_hash` (`:474`). Then `mode` routes the outcome (`:504`): `warn` surfaces and proceeds, `ask` asks, `block` denies. `REVIEW_GATE_BYPASS=1` allows in any mode and is logged (`:490`).
- The Stop nudge (`evaluate_stop`, `:544`) runs the same scope and review checks against HEAD, only when `triggers.stop_nudge` is true (`:555`). It is always soft and a bypass silences it (`:591`).

**Conditional edges, `/workflow-review`** (`workflows/workflow-review.js`). Missing `today`/`commitHash`/`principlesPath` ends the run with `bad-args` (`:22-29`). A plan without shards ends it with `no-plan` (`:256`). A plan with more than 8 shards is cut to 8 in code and the cut is added to `caps_applied` (`:262`, `clampShards` at `:205`). A reviewer that fails or returns no `findings` array marks its shard `failed` and the artifact lists it as UNREVIEWED, never as clean (`:288-291`). NITs skip verify (`:294`). If the synthesizer reports no path, the run ends with `no-artifact` (`:390`).

**Bounds.** The script never re-runs a phase or a failed shard, and the gate is single-shot. The numeric limits that exist:
- Stop nudge: max 1 per HEAD. The Stop hook fires every turn; `last_evaluated_head` is read at `hooks/review_gate.py:571` (and in the launcher, `hooks/review_gate.sh:37`) and written before the decision (`:573`), so a transient git failure on that HEAD is not retried.
- Verify: 3 skeptics per BLOCKER/CONCERN, 1 when `budget.remaining()` is below 80000 tokens (`workflow-review.js:59-61`, read at `:298`). A finding is dropped when refutes reach `ceil(skeptics / 2)` (`:194`). If every skeptic errors the finding is kept as `unverified` (`:190`).
- Shards: 8 (`MAX_SHARDS`, `:68`). The planner prompt asks for it (`:251`) and the code enforces it: `clampShards` (`:205`) cuts `plan.shards` to 8 and appends a `caps_applied` entry (planner count, shards dropped) that `review_method` carries into the artifact.
- Fix -> `/review` rounds have no cap in code. The agents report only and never auto-fix, so a human starts each round.

**State outside the chat.** `.claude/review-gate-state.json` (`last_evaluated_head`, the nudge debounce) and `.claude/review-gate-log.jsonl` (every fire and bypass), both gitignored. Review state lives in `reviews/*.md` front-matter (`commit_hash`, `status`); `/loop-bootstrap` and `/review-review` treat it as the source of truth over `_index.md`.
