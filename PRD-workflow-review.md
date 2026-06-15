---
title: /workflow-review — planner-driven multi-agent review panel
date: 2026-06-15
status: draft
owner: michaelhane
target_version: 0.4.0
roadmap_note: "Roadmap's v0.4 (graphify typed-nodes) is proposed to shift to v0.5 so this feature can take the v0.4 slot."
---

# PRD — `/workflow-review`

## Brief (5-regel)

- **Problem:** De kern van de loop — `/review` — is één agent die z'n eigen
  findings tegen 4 principes ná elkaar afvinkt. Geen onafhankelijke verificatie
  ⇒ gehallucineerde of laag-signaal findings landen in `reviews/` en vervuilen de
  compounding graph. En één agent die een grote multi-file diff door 4 lenzen
  tegelijk leest is ondiep op juist de grote, risicovolle changes — waar review
  het meeste telt.
- **Goal:** Een `/workflow-review`-commando: een planner-gedreven multi-agent
  review-panel dat (1) de review adaptief shardt op risico/grootte, (2) elke
  shard door de Karpathy-principes haalt, (3) elk finding adversarieel verifieert
  vóór het overleeft, en (4) één canoniek `reviews/`-artifact oplevert dat de
  review-gate + graphify al begrijpen.
- **Non-goal:** Vervangt `/review` niet (blijft de lichte route voor kleine
  changes). Fixt niets automatisch. Is geen kwaliteits-*plafond* (nog steeds
  presence/signal, alleen hoger-signaal). Herhaalt de 4 principes niet — leest ze
  uit `karpathy-reviewer.md`.
- **Decision:** Aanpak C (planner-matrix) bovenop de Workflow-tool. Levert als
  `commands/workflow-review.md` + `workflows/workflow-review.js`, een
  version-bumped plugin-component (0.3.2 → 0.4.0). Principes blijven SSOT in
  `karpathy-reviewer.md`. Output-schema ongewijzigd (commit_hash-stamped).
  Verify = 3 sceptici, meerderheid-weerlegt dropt.
- **Acceptance:** Live dogfood op een echte multi-file diff levert een
  schema-geldige `reviews/*.md` met het juiste commit_hash, `_index.md`
  bijgewerkt, inline-summary geprint; minstens één zwak/gehallucineerd finding
  wordt **zichtbaar** gedropt door de adversariële pass; de review-gate herkent de
  review (commit_hash-match); `/review` werkt ongewijzigd.

## Architecture

```
/workflow-review   (heavy path; /review blijft de light path)
      │
      ▼
 [scope]  git diff HEAD · status --short · rev-parse HEAD · regels/bestand
      │            + .claude/review-gate.json must_review  → risico-hints
      ▼
 Fase 1 · PLANNER  (1 agent)
      │  kiest strategie:  by-principle | by-file | matrix
      │  → shards {lens, scope, waarom} + risico per bestand
      ▼
 Fase 2 · REVIEW   (N shards parallel)        ─┐ pipeline:
      │  elk leest z'n principe uit             │ elke shard
      │  karpathy-reviewer.md  (SSOT, geen drift)│ verifieert
      │  → gestructureerde findings              │ zodra-ie
      ▼                                          │ klaar is
 Fase 3 · VERIFY   (3 sceptici/finding)         │
      │  alléén BLOCKER/CONCERN                  │
      │  meerderheid-weerlegt = drop            ─┘
      ▼   ── barrier ──
 Fase 4 · DEDUP    (pure JS, geen agent)
      │  collapse op (file, line, principe, titel)
      ▼
 Fase 5 · SYNTHESIZE (1 agent, Write)
      │  → reviews/YYYY-MM-DD-slug.md   (bestaand sjabloon, commit_hash-stamped)
      │  → reviews/_index.md  +=  one-liner
      │  → inline summary + gekozen strategie + wat er gecapt is
      ▼
 review-gate ziet 'm (commit_hash-match) · graphify indexeert 'm
```

## Phases (detail)

### Fase 0 — Scope (in de command, vóór de workflow)
Resolvet de te reviewen diff. Default = uncommitted (`git diff HEAD`). Met een
expliciete commit-range of file-set: die scope. Verzamelt en geeft als `args`
door aan de workflow:
- de diff (`git diff HEAD` of de range),
- `git status --short`,
- `git rev-parse HEAD` → **commit_hash** voor het review-artifact,
- per-bestand changed-line-counts (`git diff --numstat`),
- de inhoud van `.claude/review-gate.json` `must_review` (indien aanwezig) als
  risico-hints.

Geen uncommitted changes én geen expliciete scope ⇒ de command vraagt het de
gebruiker (net als `/review`), start de workflow niet voor niets.

### Fase 1 — Planner (1 agent)
Leest diff + per-bestand regelcounts + `must_review`-globs en kiest de
shard-strategie:
- **by-principle** — kleine diff (≤ ~3 bestanden / ≤ ~150 changed lines): 4 shards,
  één per Karpathy-principe, elk ziet de hele diff.
- **by-file** — veel bestanden, elk gematigd: één shard per bestand (of
  bestand-groep), elk reviewt z'n bestand tegen alle 4 principes.
- **matrix** — groot én risicovol: zware principes (m.n. #3 "preserve what works",
  dat elke deletion moet inspecteren) per bestand; lichte principes één keer over
  de hele diff.

Een bestand dat een `must_review`-glob matcht krijgt verhoogd risico → meer
scrutiny. Output = schema-gevalideerd plan: `{ strategy, shards: [{lens, scope,
why}], file_risk: {...}, caps_applied: [...] }`.

### Fase 2 — Review (N shards parallel)
Per shard één agent die:
- het/de toegewezen principe(s) **uit `agents/karpathy-reviewer.md` leest**
  (single source of truth — de 4 principes staan nergens in het script herhaald,
  dus geen drift),
- de toegewezen scope (hele diff of specifieke bestanden) door die lens reviewt,
- gestructureerde findings teruggeeft (schema): `{principle, severity, file, line,
  title, why, suggested_resolution}`,
- **niets schrijft** — geeft data terug.

### Fase 3 — Adversariële verify (per finding)
Elk **BLOCKER/CONCERN**-finding krijgt 3 sceptische agents die het proberen te
**weerleggen** ("twijfel = weerlegd"). ≥2 weerleggingen ⇒ drop. NITs gaan
ongeverifieerd door (3 sceptici per nit is verspilling). Dit is de kwaliteits-poort
die single-agent `/review` mist. Pipelined met Fase 2: een shard verifieert zodra
hij klaar is (geen barrier hier).

### Fase 4 — Dedup (pure JS, geen agent)
Barrier vóór synthese. Overlevende findings worden gededupliceerd op
`(file, line, principle, genormaliseerde titel)`. Cross-shard dubbele (zelfde
finding uit de by-file én de by-principle shard in een matrix) vallen samen.
Deterministisch en goedkoop — geen agent.

### Fase 5 — Synthesize (1 agent, Write)
Eén agent neemt de gededupliceerde, geverifieerde findings en:
- schrijft **één** `reviews/{YYYY-MM-DD}-{feature-slug}.md` in het **bestaande**
  sjabloon (frontmatter: `date, feature, commit_hash, files_touched,
  severity_summary, status: open, verification_needed`) — `commit_hash` uit Fase 0,
- voegt de one-liner toe aan `reviews/_index.md`,
- noteert in het artifact de **gekozen strategie + wat er gecapt is** (self-doc),
- geeft de korte inline-summary terug (blockers/concerns/nits).

De return-value van de workflow = summary + pad; de command print die.

## Cost guardrails

Planner-matrix kan ontsporen op grote diffs. Daarom:
- Planner cap't shards op ~8 (meer bestanden ⇒ groeperen tot ≤8 shards).
- Verify draait alléén op blocker/concern, niet op nits.
- Budget-bewust: minder sceptici als het token-budget krap is (`budget.remaining()`).
- **Alles wat gecapt wordt staat in het artifact** — geen stille truncatie. Dit is
  exact het eigen anti-pattern uit `empty-on-error-silent-failure` /
  reviewer-Principe 1: scheid "leeg/ingekort door een limiet" van "legitiem niets
  gevonden", en maak het zichtbaar.

## Output contract (harde eisen)

1. Conformeert exact aan het bestaande `reviews/`-schema — `commit_hash`-matching
   houdt de **review-gate** werkend, graphify ingest het, en `/review-review` kan
   het her-evalueren.
2. `reviews/_index.md` krijgt dezelfde één-regel-vorm als nu.
3. Dezelfde korte inline-summary als `/review`.
4. **Reports only, nooit auto-fix.**
5. De 4 principes blijven SSOT in `karpathy-reviewer.md`; het script herhaalt ze niet.

## Delivery

- `workflows/workflow-review.js` — het orchestratie-script (planner → review →
  verify → dedup → synth). Shipped in de plugin; de command verwijst ernaar via
  `${CLAUDE_PLUGIN_ROOT}/workflows/workflow-review.js` (scriptPath).
- `commands/workflow-review.md` — resolvet scope (Fase 0), roept de Workflow-tool
  aan met dat script + scope als `args`, print het resultaat; markeert 'm als
  heavy / opt-in; degradeert netjes naar "draai `/review`" als de Workflow-tool er
  niet is.
- `.claude-plugin/plugin.json` — **version bump 0.3.2 → 0.4.0** (delivery
  mechanism: de cache is version-gated) + `./commands/workflow-review.md`
  toevoegen aan `commands`. *(plugin.json heeft geen `workflows`-veld; het script
  wordt per pad gerefereerd, niet in het manifest geregistreerd.)*
- README — What's-in-the-box-tabel + roadmap-regel + een sectie over
  `/workflow-review`.
- COMMIT_PLAN.md — een nieuwe fase voor deze build.
- `claude plugin validate .` vóór de commit die het manifest raakt.

## Verification / acceptance (detail, runbaar)

1. Run `/workflow-review` op een echte uncommitted multi-file diff →
   `reviews/YYYY-MM-DD-<slug>.md` met `commit_hash == git rev-parse HEAD` en alle
   frontmatter-velden aanwezig.
2. `reviews/_index.md` krijgt de regel; inline-summary geprint (blocker/concern/nit).
3. Adversariële pass: weerlegde findings staan **zichtbaar** in het log (geen
   stille drop). Expliciet getest met een bewust gepland zwak/gehallucineerd
   finding dat aantoonbaar gedropt wordt — niet afhankelijk van of de echte diff
   er toevallig één oplevert.
4. In een project mét de gate aan: de gate wordt stil ná de panel-review
   (commit_hash-match).
5. `/review` ongewijzigd (regressie-check).
6. Gekozen strategie + caps staan in het artifact (self-documenting voor
   `/review-review`).

Verificatie-methode = live dogfood (zoals de review-gate is bewezen, "Live-proven
2026-06-11"), niet een geïsoleerde unit-test van de orchestratie. Pure JS-stukken
(dedup) kunnen wél los getest worden als ze gefactord zijn.

## Open implementation risks (bevestigen tijdens build, niet aannemen)

- Of `${CLAUDE_PLUGIN_ROOT}` expandeert binnen command-markdown **en** of de
  Workflow-tool die `scriptPath` slikt. Zo niet: het script inline in de command
  zetten (fallback).
- De Workflow-tool moet beschikbaar/opt-in zijn. Een slash-command waarvan de
  instructies Claude opdragen de Workflow-tool aan te roepen telt als opt-in;
  bevestigen. Bij afwezigheid: nette degradatie naar `/review`.
- Workflow-agents moeten in de cwd van het project kunnen Read/Write/Bash (voor
  `git` + `reviews/`); bevestigen tijdens de eerste live run.

## Out of scope / future (v-next)

- review-gate-koppeling die `/workflow-review` aanraadt i.p.v. `/review` voor
  diffs die `must_review`-paden raken.
- Per-finding graph-node-typering (haakt in op de v0.x graphify-typed-nodes-mijlpaal).
- `by-hunk`-sharding (fijner dan `by-file`) voor enorme single-file changes.
