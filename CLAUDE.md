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
- Tests: `python tests/test_review_gate.py` (stdlib only). Full plan + DoD: COMMIT_PLAN Phase J (v0.3.0) + Phase K (v0.3.1).
- **Live-proven 2026-06-11**: both triggers fired in a real session (merge-gate `ask` + stop-nudge; evidence in the COMMIT_PLAN DoD-close + `reviews/2026-06-11-dod-close-prd-fire-test.md`). First opt-in: chief-of-staff `f28c79f`. NB: `claude plugin details` showing "Agents (0)" is a harmless display quirk — the karpathy-reviewer launches fine.

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
