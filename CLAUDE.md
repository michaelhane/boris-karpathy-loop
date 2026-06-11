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
- After changing `hooks/` or `.claude-plugin/*.json`: re-install with `claude plugin update boris-karpathy-loop@boris-karpathy-loop`, then **restart Claude** (plugin hooks load at session start). The marketplace is a local Directory → no GitHub push needed for local use.
- Tests: `python tests/test_review_gate.py` (stdlib only). Full plan + DoD: COMMIT_PLAN Phase J (v0.3.0) + Phase K (v0.3.1).
- **Live-proven 2026-06-11**: both triggers fired in a real session (merge-gate `ask` + stop-nudge; evidence in the COMMIT_PLAN DoD-close + `reviews/2026-06-11-dod-close-prd-fire-test.md`). First opt-in: chief-of-staff `f28c79f`. NB: `claude plugin details` showing "Agents (0)" is a harmless display quirk — the karpathy-reviewer launches fine.
