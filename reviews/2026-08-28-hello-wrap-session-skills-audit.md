---
date: 2026-08-28
feature: hello-wrap-session-skills-audit
commit_hash: 6ae72797e9417d2161422156576941e3e98a7a69
files_touched:
  - ~/.claude/skills/hello/SKILL.md (extern — lokaal-only, niet leesbaar vanuit deze sessie)
  - ~/.claude/skills/wrap-session/SKILL.md (extern — lokaal-only, niet leesbaar vanuit deze sessie)
severity_summary:
  blocker: 1
  concern: 4
  nit: 3
status: open
verification_needed:
  - file-level pass van beide SKILL.md's zodra ze geversioneerd zijn (frontmatter/allowed-tools, stappen-idempotentie, is de dispatcher echt read-only, zijn de hook-overlaps uit C3 en de graphify-syntax uit C4 in de echte files aanwezig)
  - bevestig of /orde-stellen en /pre-flight-sync nog commands zijn of ook al skills — bepaalt hoe de referentie-tabel-fix (C4) eruitziet
  - bevestig welke allow-entries in chief-of-staff settings.local.json door de wrap-session-harvest kwamen vs. handmatige "always allow"-clicks (attributie voor C2)
---

# Review: audit van de /hello- en /wrap-session-skills (evidence-based)

## Context

Gevraagd: "audit 2 commands; hello en wrap-session". Beide blijken personal
**skills** op de lokale machine (`Skill(hello)` / `Skill(wrap-session)` in
`chief-of-staff/.claude/settings.local.json:130,148`) — ze staan in geen enkele
repo en niet in de claude.ai-synced skills, dus de files zelf waren vanuit deze
remote sessie onleesbaar. Dit is daarom, naar het precedent van de
2026-06-11 DoD-close review, geen diff-review maar een **evidence-audit**: alles
wat beide repos over de twee skills vastleggen is naast elkaar gelegd —
chief-of-staff (CLAUDE.md, PROJECT_STATE.md, hooks-PRD
`docs/specs/2026-05-28-hooks-consolidated-prd.md`, settings, handoffs) en deze
repo (COMMIT_PLAN Phase K, README, commit-historie t/m `6ae7279` van vandaag) —
en beoordeeld langs de vier principes uit `agents/karpathy-reviewer.md`. Dat de
file-level audit niet kón, is meteen de blocker.

## Findings

### [BLOCKER] De hele globale discipline-laag is ongeversioneerd
- **Principle:** 4 (geen verifieerbare bron — en single point of failure)
- **Where:** `~/.claude/skills/hello/`, `~/.claude/skills/wrap-session/`, de 5 hook-scripts in `~/scripts/` (chief CLAUDE.md:610-618), globale `~/.claude/settings.json`
- **Why it matters:** alles wat de discipline *afdwingt* is geversioneerd en reviewbaar (deze plugin, review-gate config, specs), maar de orkestratie zelf heeft geen git-historie, geen review-mogelijkheid en geen backup-bewijs. Eén disk-failure wist de laag; en deze audit-opdracht strandde er vandaag concreet op. De hooks-PRD's eigen principe ("knowledge captured in MEMORY ≠ knowledge enforced in code") heeft een variant: knowledge in unversioned files ≠ auditeerbaar.
- **Suggested resolution:** een `claude-home` repo — zie Fix-plan stap 1.

### [CONCERN] /wrap-session heeft nog steeds geen review-stap
- **Principle:** 4
- **Where:** COMMIT_PLAN.md:729-733 ("even `/wrap-session` has no review step"); chief-of-staff `.claude/review-gate.json` (enige opt-in, 3 must-review paths)
- **Why it matters:** de stop_nudge (v0.3.1) is het vangnet, maar die is opt-in per project en dekt nu alleen chief-of-staff. In elke andere repo sluit wrap-session sessies af zonder review-check — precies de orphan-gap die Phase K beschrijft, alleen nu structureel bekend en toch open.
- **Suggested resolution:** één stap in wrap-session zelf: "code-commits sinds laatste review? → `/review` of één regel rationale". SSOT-schoon via een `--check` CLI-mode op `hooks/review_gate.py` (zie Fix-plan stap 3) i.p.v. de gate-logica in de skill dupliceren.

### [CONCERN] Permission-harvest is add-only; de allow-list rot
- **Principle:** 1
- **Where:** chief-of-staff `.claude/settings.local.json` — 174 allow-entries, `deny`/`ask` leeg; daartussen meerdere brede exec-, netwerk- en push-wildcards in allow (waarvan één ook force-push matcht), naast tientallen dode one-off literals (volledige commando's met UUID's en `/tmp`-paden). De concrete patronen staan bewust niet in deze publieke file — zie de settings-file zelf (privé repo)
- **Why it matters:** wat de harvest vandaag toevoegde was voorbeeldig scoped (commit `6ae7279`: 3 patronen, allemaal read-only), maar er is geen bewijs van een prune/escalatie-kant. Add-only → list rot, en de rot camoufleert de brede wildcards die er wél toe doen.
- **Suggested resolution:** harvest-stap uitbreiden tot tweerichtingsverkeer: prune dode literals, escaleer netwerk/exec-wildcards naar `ask` of versmald patroon; leg de bewuste keuzes per breed patroon vast. Zie Fix-plan stap 2.

### [CONCERN] /hello's detecties overlappen inmiddels met geshipte hooks
- **Principle:** 2/3
- **Where:** chief CLAUDE.md:497-507 (detectielijst) vs. CLAUDE.md:608-622 (Hooks Consolidated — SHIPPED 2026-05-29) en CLAUDE.md:633 (graphify's eigen post-commit hook sinds 0.8.39)
- **Why it matters:** Hook 6 (sibling-scan) automatiseert exact /hello's handoff-stap 6b (zo benoemd in de hooks-PRD:58-61); Hook 3 dekt de sync-check bij SessionStart; en de graph rebuildt automatisch post-commit, waarmee de ">5 commits stale"-detectie een failsafe is geworden. Als hello.md hier niet op is bijgewerkt geeft hij dubbele signalen en verouderde adviezen — dead weight in de dispatcher.
- **Suggested resolution:** hello.md de-overlappen: hook-output tonen i.p.v. zelf scannen, stale-detectie ombouwen tot hook-health-check. Zie Fix-plan stap 4. Verifiëren in de echte file (file-level pass).

### [CONCERN] Referentie-drift in chief CLAUDE.md
- **Principle:** 3
- **Where:** chief CLAUDE.md:524 (`~/.claude/commands/hello.md` terwijl permissions `Skill(hello)` tonen) en CLAUDE.md:505 (`graphify . --update` terwijl de canonieke syntax `graphify update .` is — als echte CLI surface geverifieerd in reviews/2026-05-30-v0.2.3-hook-fix.md)
- **Why it matters:** de command→skill-migratie is niet in de referentie-tabel geland; wie de tabel volgt edit mogelijk een dode file. En óf de CLAUDE.md-sectie óf /hello zelf suggereert een commando dat niet (meer) bestaat. Precies de "duplicated truth diverges"-gotcha die `skills/boris-cherny-way/SKILL.md` zelf benoemt.
- **Suggested resolution:** tabel + syntax fixen in chief CLAUDE.md; daarbij meteen de status van /orde-stellen en /pre-flight-sync vaststellen. Zie Fix-plan stap 5.

### [NIT] "Master ahead of origin > 2" is een onverklaard hardcoded getal
- **Principle:** 1
- **Where:** chief CLAUDE.md:503
- **Why it matters:** waarom 2? Zonder rationale is de drempel niet te herijken en leest hij als toeval.
- **Suggested resolution:** één regel rationale bij de drempel, of een benoemde variabele in de skill.

### [NIT] /wrap-session is nergens gedocumenteerd in chief CLAUDE.md
- **Principle:** 3
- **Where:** chief CLAUDE.md — /hello heeft een eigen sectie (r. 495-533), /wrap-session komt in het hele document niet voor (alleen in de hooks-PRD en één handoff)
- **Why it matters:** de helft van het sessie-ritueel is ongedocumenteerd in het canonieke doc; nieuwe sessies kennen wel de start- maar niet de eind-verplichtingen.
- **Suggested resolution:** korte /wrap-session-sectie naast de /hello-sectie, of één "sessie-ritueel"-sectie die beide dekt.

### [NIT] Twee definities van het einde-ritueel — welke is SSOT?
- **Principle:** 3
- **Where:** `skills/boris-cherny-way/SKILL.md` ("End of session": PROJECT_STATE update, CHANGELOG append, guides update) naast de wrap-session-skill zelf
- **Why it matters:** twee beschrijvingen van hetzelfde ritueel divergeren over tijd; de start-kant heeft wél een voorrangsregel ("simulate /ctx if no command exists"), de eind-kant niet.
- **Suggested resolution:** pointer in één richting: boris-cherny-way = generiek ritueel, wrap-session = de implementatie die voorgaat.

## What was done well

Het dispatcher-model van /hello (detecteren → suggereren, gedefinieerde
prioriteit, nooit zelf beslissen) is sterk design. De loop tussen de twee
skills werkt aantoonbaar: wrap-session schreef vandaag nog het "Volgende
sessie — PRD"-blok met paste-ready kickoff (chief PROJECT_STATE.md:153-166),
precies waar /hello op aanhaakt. De harvest van vandaag was voorbeeldig scoped
(3 patronen, allemaal read-only, nette commit message). En het
handoff-patroon is bewust handmatig gehouden, met vastgelegde rationale in de
hooks-PRD ("auto-commit hooks — overkill").

## Fix-plan

Volgorde gekozen op fundament-eerst: stap 1 maakt al het andere reviewbaar.
Stap 2 kan desnoods vandaag al, los van de rest. Totaal ~2,5u — zelfde maat
als de hooks-consolidated sessie.

1. **`claude-home` repo (de blocker) — ~45-60 min.** Nieuwe private repo met
   `skills/hello/`, `skills/wrap-session/` (+ overige personal skills),
   `scripts/` (de 5 hook-scripts uit `~/scripts/`), de globale
   `settings.json` en een `deploy.py` die repo → live-locaties kopieert met
   een `--check` drift-mode — hetzelfde patroon als chief-of-staff's
   `deploy_drift_check.py` + `config/deploy_facts.yaml`, dus bewezen huisstijl.
   Aparte repo (geen dir in chief-of-staff): de laag is machine-globaal, niet
   project-gebonden, en een aparte repo kan aan remote sessies gekoppeld
   worden — dat had deze audit file-level gemaakt. Optioneel: skills ook naar
   claude.ai syncen zodat remote sessies ze meekrijgen. Drift-check daarna in
   wrap-session of een SessionStart hook hangen.
2. **Permission-hygiëne chief-of-staff — ~15 min, kan direct.** Eenmalig:
   dode one-off literals verwijderen; de brede ssh/curl-wildcards versmallen
   naar het ene host-patroon dat je echt gebruikt, of naar `ask`; de brede
   push-wildcard als bewuste keuze vastleggen (houden = ok, maar dan als
   keuze, niet als aanslibsel). Structureel: harvest-stap in wrap-session
   uitbreiden met prune + escalatie-voorstel (klein `permission_hygiene.py`
   in claude-home dat rapporteert; jij beslist).
3. **Review-stap in wrap-session — ~30 min.** Plugin-kant: `--check`
   CLI-mode op `hooks/review_gate.py` (kleine fase; houdt de
   fresh-review-vs-HEAD-logica SSOT). Skill-kant: één stap "run de check in
   repos met code-commits; bij rood → `/review` of één regel rationale".
   Daarnaast review-gate.json uitrollen naar meer projecten dan alleen
   chief-of-staff.
4. **/hello de-overlappen met hooks — ~20 min.** Stap 6b (handoff-scan)
   vervangen door "toon wat Hook 6 meldde" (of als guarded fallback);
   sync-detectie laten verwijzen naar Hook 3-output en alleen de ahead-kant
   behouden, mét rationale voor de drempel; graphify-stale-detectie ombouwen
   tot hook-health failsafe met de juiste syntax (`graphify update .`).
5. **Doc-fixes chief CLAUDE.md — ~15 min.** Referentie-tabel naar
   skills-paden; `graphify . --update` → `graphify update .`; korte
   /wrap-session-sectie; SSOT-pointer tussen boris-cherny-way en
   wrap-session. Daarna in claude-home: `/review` op de skills-commits =
   de file-level audit die nu geblokkeerd was.

### Kickoff — plak als eerste bericht van de lokale sessie

```text
Voer het fix-plan uit reviews/2026-08-28-hello-wrap-session-skills-audit.md
(boris-karpathy-loop) uit, in volgorde: (1) claude-home repo — verplaats
~/.claude/skills/hello + wrap-session, de 5 hook-scripts uit ~/scripts en de
globale settings.json naar een nieuwe private repo met deploy.py + drift-check
(patroon: chief-of-staff deploy_drift_check.py); (2) permission-hygiëne
chief-of-staff settings.local.json — prune dode literals, netwerk/exec-wildcards
versmald of naar ask, brede push-wildcard als bewuste keuze; (3) review-stap in wrap-session via
een --check mode op review_gate.py; (4) /hello de-overlappen met Hooks 3/6 en
de graphify post-commit hook; (5) chief CLAUDE.md doc-fixes (tabel, syntax,
wrap-session-sectie). Sluit af met /review op de claude-home commits — dat is
meteen de file-level audit van beide skills.
```
