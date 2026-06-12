# Commit Plan — boris-karpathy-loop v0.1

This is the rollout plan for shipping `boris-karpathy-loop` as your first publish.
Work it commit by commit. Each commit is small enough to review and revert in
isolation.

## Phase A — Local repo setup

### A1. Initialize the repo
```bash
cd ~/Projects
mkdir boris-karpathy-loop
cd boris-karpathy-loop
git init
```

### A2. Drop in all files generated in this session
Copy the files Claude produced into this folder, preserving structure:
```
boris-karpathy-loop/
├── README.md
├── LICENSE
├── COMMIT_PLAN.md          # this file
├── .gitignore
├── .gitmodules
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/boris-cherny-way/SKILL.md
├── agents/
│   ├── karpathy-reviewer.md
│   └── karpathy-tutor.md
├── commands/
│   ├── review.md
│   ├── review-review.md
│   ├── loop-bootstrap.md
│   └── tutor.md
└── scripts/
    ├── extract_patterns.py
    └── regen_skill.py
```

### A3. Add the-boris-cherny-way as submodule
```bash
git submodule add git@github.com:michaelhane/the-boris-cherny-way.git the-boris-cherny-way
```
(Adjust URL if your KB repo is named or located differently. If not yet on GitHub, push that one first.)

### A4. First commit
```bash
git add .
git commit -m "chore: initial scaffold for boris-karpathy-loop v0.1

- plugin manifest, marketplace.json
- boris-cherny-way skill (distilled from KB)
- karpathy-reviewer subagent
- /review, /review-review, /loop-bootstrap commands
- extract_patterns.py for promoting findings to anti-patterns
- README with full attribution
- the-boris-cherny-way as submodule"
```

## Phase B — Test locally before pushing public

### B0. Validate manifests against the plugin schema (also recommended BEFORE A4)
```bash
claude plugin validate .
```
Expected: `marketplace.json` and `plugin.json` both pass schema validation.

This catches shape errors that plain JSON-parse validation misses — most
notably, `author` (in `plugin.json`) and `owner` (in `marketplace.json`) must
be objects of the form `{ "name": "...", "url": "..." }`, not bare strings.
v0.1.0 was committed with both as strings; they parsed fine but `claude
plugin install` rejected them at install time. Running `validate` before A4
would have caught it pre-commit.

Fallback if the CLI isn't on PATH: invoke the `plugin-dev:plugin-validator`
agent in Claude Code with the project root as input.

### B1. Install the plugin locally
From inside Claude Code:
```
/plugin marketplace add /absolute/path/to/boris-karpathy-loop
/plugin install boris-karpathy-loop@boris-karpathy-loop
```

### B2. Smoke test in the-boris-cherny-way (your dogfood pilot)
```bash
cd the-boris-cherny-way
# In Claude Code:
/loop-bootstrap
```
Expected: it reports "no review history yet" gracefully and lets you proceed.

### B3. First real review on a meaningful change
Make a non-trivial edit to one of the guides, then:
```
/review
```
Expected:
- A new file `reviews/YYYY-MM-DD-{slug}.md` exists
- `reviews/_index.md` has one line
- The chat shows a 4-line summary (counts of blockers/concerns/nits)

### B4. Validate the script
```bash
# After closing the review (manually edit status: closed in frontmatter):
python scripts/extract_patterns.py \
    --reviews-dir reviews/ \
    --target guides/anti-patterns.md \
    --dry-run
```
Expected: dry-run prints what it would append without modifying files.

### B5. Run-it-twice idempotency check
```bash
python scripts/extract_patterns.py --reviews-dir reviews/ --target guides/anti-patterns.md
python scripts/extract_patterns.py --reviews-dir reviews/ --target guides/anti-patterns.md
```
Expected: second run says "Nothing new to add. Skipped N already-present findings."

### B6. Test the regen script on the KB submodule
```bash
git submodule update --init the-boris-cherny-way
python scripts/regen_skill.py
git diff skills/boris-cherny-way/SKILL.md
```
Expected: SKILL.md updated with current date and a guide listing matching your KB's `guides/` folder.

### B7. Tutor smoke test
In Claude Code, in any project:
```
/tutor
```
Expected: tutor asks what you want to understand, doesn't immediately start lecturing.

Then try a real one:
```
/tutor explain hooks in the boris-cherny-way KB workflow
```
Expected: diagnose-then-teach loop, not a wall of text. Ends with three-line footer (You can now / Try this / Next).

## Phase C — Publish

### C1. Create the GitHub repo
```bash
gh repo create boris-karpathy-loop \
    --public \
    --description "Boris workflow + Karpathy review subagent + Graphify-friendly compounding loop for Claude Code" \
    --source=. \
    --push
```
(Or via the GitHub UI if you prefer.)

### C2. Add topics for discoverability
```bash
gh repo edit --add-topic claude-code,claude-plugin,code-review,llm-tooling,karpathy
```

### C3. Tag the release
```bash
git tag -a v0.1.0 -m "Initial release"
git push origin v0.1.0
gh release create v0.1.0 --generate-notes
```

### C4. Announce (optional)
- Post on X with link, tag @karpathy and @forrestchang? Up to you.
- Submit to claude code marketplace registries (if/when they exist).

## Phase D — Validation in Galactische Vriendjes (after dogfood)

### D1. Install in target project
```bash
cd ~/Projects/galactische-vriendjes
graphify .                      # if not yet done
git add graphify-out/
graphify hook install
git commit -m "chore: graphify baseline"
```

### D2. Check existing CLAUDE.md doesn't conflict
Read your current Galactische Vriendjes CLAUDE.md. If there are rules that
contradict Karpathy's principles (e.g., a rule saying "don't ask, just ship"),
note them and decide. Document the resolution.

### D3. First review session
Make a feature change, then:
```
/loop-bootstrap
# work
/review
```

### D4. Two-week dogfood metrics
Track in `reviews/_metrics.md`:
- Number of reviews run
- findings_per_review (mean)
- % of findings that became `status: closed` within 7 days
- Subjective: did review noise dominate signal?

After 2 weeks, decide:
- Roll out to Chef2 Gemini, OOTA?
- Adjust severity thresholds in karpathy-reviewer.md?
- Cut a v0.2 with adjustments?

## Open questions for you

1. Is `michaelhane` your GitHub handle? If not, sweep `plugin.json`,
   `marketplace.json`, `README.md`, and `.gitmodules` for the placeholder.
2. URL in the Karpathy reference inside README — the X post URL I used is a
   guess at format. Verify before publishing.
3. Boris Cherny attribution: are you OK with the wording "has not endorsed"?
   Some prefer "no affiliation." Adjust to your preference.
4. License of any future scripts you add — keep MIT unless there's a reason
   not to.

## Definition of done for v0.1.0

- [ ] All files in place locally
- [ ] Plugin installs cleanly via `/plugin install`
- [ ] `/loop-bootstrap` runs in a fresh project without crashing
- [ ] `/review` produces a valid review file on a real change
- [ ] `extract_patterns.py --dry-run` works
- [ ] README attribution verified by you
- [ ] Repo public on GitHub
- [ ] v0.1.0 tag pushed

## Phase E — v0.2 release

v0.2 adds two operational commands (`/setup-graphify`, `/diagnose-loop`) that
encode the day-one dogfood lessons. Strict additions only — no changes to
existing v0.1 commands, agents, or skills.

### E1. Validate the manifest (B0 gate)
```bash
claude plugin validate .
```
Catches schema errors before install attempts. Enforced by COMMIT_PLAN B0.

### E2. Manual test: `/setup-graphify` in a fresh non-home project
A natural target is `bo-karpa-loop` itself — per `the-boris-cherny-way/guides/loop-workflow.md` section 12 the repo sits as plugin ✅ but graphify ⏸:
```
cd C:\Users\micha\Projects\bo-karpa-loop
claude
# inside claude:
/boris-karpathy-loop:setup-graphify
```
Expected: state-detection report, decisions prompt only for what couldn't be
auto-detected, cost estimate before extraction, per-step confirmation, ends
with `git add` + a suggested commit message (no auto-`git commit`).

### E3. Manual test: `/diagnose-loop` identifies a known issue
Force a failure first — e.g. delete `graphify-out/GRAPH_REPORT.md` or
temporarily unset `GEMINI_API_KEY` in the current shell — then run:
```
/boris-karpathy-loop:diagnose-loop
```
Expected: ⚠️ or ❌ on the broken check, exact fix command in a code block,
zero modifications made by the diagnose command itself.

### E4. `/review` on the cumulative v0.2 diff
From inside `bo-karpa-loop`:
```
/boris-karpathy-loop:review
```
The diff is the four v0.2 commits. Address any substantial findings in
additional commits before tagging.

### E5. Tag v0.2.0
```
git tag -a v0.2.0 -m "v0.2.0 — /setup-graphify + /diagnose-loop"
git push origin v0.2.0   # only when/if the repo is public
```

## Definition of done for v0.2.0

- [x] `commands/setup-graphify.md` exists with frontmatter and clear step-by-step instructions
- [x] `commands/diagnose-loop.md` exists with frontmatter and clear step-by-step instructions
- [x] `.claude-plugin/plugin.json` registers both new commands; version bumped to `0.2.0`
- [x] `README.md` updated: Quick start + "What's in the box" table
- [x] `COMMIT_PLAN.md` has Phase E for v0.2 release
- [x] `claude plugin validate .` passes (B0 gate)
- [x] Manual test E2: `/setup-graphify` walks through full flow without errors in a fresh non-home project
- [x] Manual test E3: `/diagnose-loop` correctly identifies a known issue and outputs the right fix command
- [x] No auto-fixes in `/diagnose-loop` — read-only verified
- [x] No API keys logged anywhere — values never echoed
- [x] `/review` on cumulative v0.2 diff has no unaddressed substantial findings (4 concerns surfaced, all addressed in `130b720`)
- [x] v0.2.0 tag created (push when/if going public) — local tag at `130b720`

## Phase F — v0.2.1 patch release

v0.2.1 fixes the karpathy-reviewer file-write fragility surfaced
during v0.2 dogfood (multi-KB markdown via PowerShell heredoc hits
the Windows command-line length limit), plus the 3 nits deferred
during the v0.2 release.

### F1. Validate manifest (B0 gate)
```bash
claude plugin validate .
```
Same gate as B0/E1. Caught nothing this time — no schema-shape
changes between 0.2.0 and 0.2.1.

### F2. Smoke test the reviewer file-write fix
The smoke test for the Write-tool addition is the reviewer
itself: if it can persist its own review of the v0.2.1 commits,
the fix works. Empirical, not isolated. Sufficient for a
slash-command plugin where adding a controlled-reproduction
harness would dominate the cost of the fix.

```
/boris-karpathy-loop:review
# range prompt: HEAD~3..HEAD
```

Expected: file `reviews/2026-05-07-v0.2.1-*.md` written without
timeout, summary printed inline, no parser-abort.

### F3. Address review findings
The v0.2.1 review (`reviews/2026-05-07-v0.2.1-fixups.md`)
surfaced:
- **0 blockers**
- **1 concern** (verification gap): the Write-tool fix is
  reasoned but not isolated-reproduced. Disposition: not
  addressed in code. The successful F2 smoke test is the
  empirical verification; an isolated harness would be overkill
  for a slash-command plugin.
- **2 nits**:
  1. Duplicated naming-note prose across `setup-graphify.md`
     and `diagnose-loop.md`. Disposition: leave as-is. Each
     command file is self-contained; a 2-line note in both is
     reasonable for clarity.
  2. `COMMIT_PLAN.md` stale + missing v0.2.1 tag.
     Disposition: addressed by this very commit and the tag
     immediately after.

### F4. Tag v0.2.1
```
git tag -a v0.2.1 -m "v0.2.1 — reviewer file-write fix + 3 nits"
git push origin v0.2.1   # only when/if the repo is public
```

## Definition of done for v0.2.1

- [x] `agents/karpathy-reviewer.md` frontmatter includes `Write` tool
- [x] `agents/karpathy-reviewer.md` body explicitly directs Write-tool usage for the review artifact
- [x] 3 deferred nits from v0.2 review addressed (tautological row dropped, naming note added, `--reinstall` → `upgrade`)
- [x] `.claude-plugin/plugin.json` bumped to `0.2.1`
- [x] B0 schema validation passed before manifest commit
- [x] F2 smoke test successful — `reviews/2026-05-07-v0.2.1-fixups.md` written on first try, no timeout
- [x] Two unaddressed review findings have written justifications (F3)
- [x] v0.2.1 tag created

## Phase G — v0.2.2 patch release

v0.2.2 fixes a **broken remediation command** shipped in v0.2.1 and
caught by finally running the v0.2.1 review's deferred verification step.

### The bug

The v0.2 review nit "`--reinstall` silently bumps the version" was fixed
in v0.2.1 by swapping `uv tool install --reinstall` → `uv tool upgrade
--with` in the missing-extras branch of both `/diagnose-loop` and
`/setup-graphify`. **`uv tool upgrade` has no `--with` flag.** The
shipped fix errors out:

```
$ uv tool upgrade graphifyy --with anthropic
error: unexpected argument '--with' found
```

The v0.2.1 review recorded this exact line as verification_needed #3
("confirm `uv tool upgrade … --with` adds the extras"). Phase F3
dispositioned it as "covered by the F2 smoke test" — but F2 only
exercised the reviewer's Write path, never the setup/diagnose upgrade
command. **The disposition was a false-closed verification:** the
finding was written down, then waved through without being run. This is
the loop catching its own gap — principle 4 ("absence of verification is
itself a finding") applied to a finding that existed on paper but was
dispositioned away unverified.

### G1. Verify the correct command empirically

`uv tool install --with` is the documented way to add packages to an
existing tool; base-version upgrades are opt-in via `-U`/`--upgrade`.
Confirmed with a throwaway tool (the real `graphifyy` was never touched):

```
uv tool install 'cowsay==5.0'            # cowsay v5.0
uv tool install cowsay --with iniconfig  # cowsay v5.0 [with: iniconfig]  ← base version unchanged
uv tool uninstall cowsay
```

Base version stayed `5.0`; the extra was added. So `uv tool install
graphifyy --with anthropic --with openai` matches the original intent
(add extras, no version bump) without the invalid flag.

### G2. Fix both command files

- `commands/diagnose-loop.md` — missing-extras branch → `uv tool install
  … --with …`, prose corrected with an explicit "`upgrade` has no
  `--with`" warning.
- `commands/setup-graphify.md` — same.

Historical review artifacts under `reviews/` are left untouched — they
are the record, including the v0.2 review line that first recommended the
wrong command.

### G3. Validate manifest + bump

```
claude plugin validate .   # passed
```
`.claude-plugin/plugin.json` → 0.2.2.

### G4. Re-review + tag

```
/boris-karpathy-loop:review     # range: the v0.2.2 working diff
git tag -a v0.2.2 -m "v0.2.2 — fix invalid 'uv tool upgrade --with' in /diagnose-loop + /setup-graphify"
```

## Definition of done for v0.2.2

- [x] Both command files use `uv tool install --with` for the missing-extras branch
- [x] Prose in both files warns that `uv tool upgrade` has no `--with` flag
- [x] Correct command verified empirically (throwaway tool, base version unchanged)
- [x] `.claude-plugin/plugin.json` bumped to `0.2.2`
- [x] B0 schema validation passed before manifest commit
- [x] v0.2.1 review status reconciled (verification_needed #3 was a real bug, now fixed)
- [x] `/review` on the v0.2.2 diff has no unaddressed substantial findings — 0 blockers, 0 concerns, 2 nits (`reviews/2026-05-30-v0.2.2-uv-tool-install-fix.md`); both nits are bookkeeping and dispositioned
- [x] v0.2.2 tag created

## Phase H — v0.2.3: post-commit graphify hook reliability

Surfaced during the v0.2.2 wrap: the post-commit hook fired with
`ignored null byte in input` and did **not** refresh `GRAPH_REPORT.md`
(it stayed at the previous commit until `graphify update .` was run by
hand). The auto-update is unreliable on Windows/Git-Bash.

- **Problem**: the graphify post-commit hook errors (`ignored null byte in input`) on Windows and leaves `GRAPH_REPORT.md` stale after a commit, so the graph silently drifts from HEAD until someone runs `graphify update .` manually.
- **Goal**: a post-commit hook that reliably refreshes `graph.json` + `GRAPH_REPORT.md` after each commit on Windows Git-Bash — or fails loudly instead of silently.
- **Non-goal**: rewriting graphify itself; changing hook behavior on macOS/Linux (only the Windows null-byte path is in scope).
- **Decision**: inspect `.git/hooks/post-commit` (~line 23); the null byte almost certainly comes from a command-substitution reading binary/CRLF `git` output — sanitize (`tr -d '\0'`) or change the capture. Keep it AST-only (`graphify update .`, no API cost).
- **Acceptance**: make a trivial commit on Windows; confirm `GRAPH_REPORT.md`'s "Built from commit" matches the new HEAD with no manual step and no `ignored null byte` warning.

### Root cause (confirmed — the brief's "Decision" hypothesis was incomplete)

The null byte does **not** come from CRLF `git` output. It comes from the
hook's *interpreter detection* (hook lines 18–47). On Windows/Git-Bash
`command -v graphify` returns the **extension-less** path
(`/c/Users/.../graphify`) even though the real launcher is `graphify.exe`
— a PE32+ binary. The `case` at ~line 21 only treats `*.exe` specially, so
the extension-less path falls through to `head -1 "$GRAPHIFY_BIN"`, which
reads the binary's `MZ` header; `$(...)` then strips the embedded NUL and
bash warns `ignored null byte in input`. Reproduced 1-for-1.

Investigation surfaced a **second, larger problem the brief missed**: even
with the warning suppressed, the hook's fallback runs a *system*
`python`/`python3`, neither of which can `import graphify` (it is
uv-isolated under `AppData/Roaming/uv/tools/graphifyy/`). So the detached
rebuild would hit `exit 0` and silently no-op. Evidence:
`~/.cache/graphify-rebuild.log` did not exist — the background rebuild had
**never run** on this machine. The graph stayed fresh only because
`graphify update .` was run by hand. Fixing the null byte alone would not
have satisfied the acceptance test.

### H1. Fix approach — drive the CLI, don't reconstruct the interpreter

Rather than patch the shebang read, short-circuit the whole detection on
the Windows `.exe` path and call the launcher directly:
`graphify update .` (an AST-only CLI command, "no LLM needed" per
`graphify --help`). The `.exe` launcher resolves its own venv interpreter,
so no system-python guessing is needed. This kills **both** problems at
once and is a no-op on macOS/Linux (the `*.exe`/sibling-`.exe` guard never
matches there), honoring the non-goal.

### H2. Durable artifact: `scripts/fix_graphify_hook.py`

`.git/hooks/` is not version-controlled and `graphify hook install`
overwrites it, so the fix lives as a re-runnable patcher (decision:
"repo-script + live patch"). It inserts the short-circuit after the
`GRAPHIFY_BIN=$(command -v graphify …)` anchor. Idempotent (second run =
"already patched"); fails loudly if the hook is absent, not
graphify-installed, or its shape drifted so the anchor is gone. Mirrors the
existing `scripts/*.py` style (`--dry-run`, argparse). Passes `ruff`,
`ruff format`, and `ty`.

### H3. Validate + bump

```
claude plugin validate .        # B0 gate
```
`.claude-plugin/plugin.json` → 0.2.3.

### H4. Acceptance test = the v0.2.3 release commit itself

The release commit triggers the patched hook. Watch for: no
`ignored null byte` warning, `~/.cache/graphify-rebuild.log` created, and
`GRAPH_REPORT.md`'s "Built from commit" advancing to the new HEAD with no
manual `graphify update .`.

### H5. Review dispositions (`reviews/2026-05-30-v0.2.3-hook-fix.md` — 0 blockers, 1 concern, 3 nits)

- **CONCERN — acceptance test unrun (Principle 4):** the only substantial finding. Resolved by H4 — the v0.2.3 release commit fires the hook; evidence (no null-byte warning, log completion line + node count, stamp == new HEAD) captured below before the box is checked. Not dispositioned away.
- **NIT 1 — dropped `GRAPHIFY_FORCE`/`--force` (Principle 3):** *not* a silent delta. `graphify update` documents `GRAPHIFY_FORCE=1` env support, and the env var is inherited by the detached `nohup` subprocess, so the original behavior is preserved; `--force` recovers it explicitly if ever needed. Left as-is.
- **NIT 2 — implicit post-commit CWD (Principle 1):** identical to the original hook's assumption (git runs `post-commit` at the worktree root, so `.` is the repo). No regression. Left as-is.
- **NIT 3 — idempotency reinstall note (Principle 4):** already documented in the `scripts/fix_graphify_hook.py` module docstring ("run it again after any reinstall"). No change.

## Definition of done for v0.2.3

- [x] Root cause confirmed empirically (extension-less `command -v` + binary `.exe`; reproduced the warning)
- [x] Second failure mode found and documented (uv-isolated graphify unimportable by system python; rebuild never ran)
- [x] `scripts/fix_graphify_hook.py` created — idempotent, fail-loud, `--dry-run`, lint/format/type clean
- [x] Live `.git/hooks/post-commit` patched; re-running the script is a no-op
- [x] `.claude-plugin/plugin.json` bumped to `0.2.3`
- [x] `claude plugin validate .` passes (B0 gate)
- [x] Acceptance: v0.2.3 release commit `c40ea11` fired the hook — no null-byte warning; `~/.cache/graphify-rebuild.log` created with `Rebuilt: 290 nodes, 294 edges`; `GRAPH_REPORT.md` "Built from commit" == `c40ea115` (new HEAD), no manual step
- [x] `/review` on the v0.2.3 diff has no unaddressed substantial findings (0 blockers; 1 concern resolved by the acceptance test above; 3 nits dispositioned in H5)
- [x] v0.2.3 tag created

## Phase I — v0.2.4: reconcile open reviews + close the status-drift loop

Discovered by running Phase D4 (dogfood metrics, `reviews/_metrics.md`): two
reviews sat `status: open` while their findings were already fixed in code —
the **false-open**, mirror of the v0.2.1→v0.2.2 false-close. The loop already
had the machinery to prevent it (`/review-review` writes status back) but
nothing *triggered* it, and `/loop-bootstrap` trusted `_index.md`'s prose over
the per-review `status:` front-matter.

**Brief**
- **Problem:** review `status:` drifts from reality — fixes ship without the
  review/`_index` being flipped, so `_index` lies and loop-bootstrap mis-reports.
- **Goal:** reconcile the two open reviews accurately, and make the drift
  detectable at session start so it self-corrects.
- **Non-goal:** no new severity rubric, no `close_finding.py` script (YAGNI at 4
  reviews), no change to `/review`'s finding logic.
- **Decision:** front-matter `status:` is the source of truth, `_index.md` is
  derived. `/loop-bootstrap` detects drift; `/review-review` (already writes
  back) reconciles it; same-commit flipping is the happy path.
- **Acceptance:** both open reviews resolved with attributed footers; `_index`
  synced; loop-bootstrap flags a stale-open on its next run; `claude plugin
  validate .` passes; `/review` on the diff has no unaddressed substantial finding.

### I1. Reconcile the two open reviews
- `v0.2-setup-and-diagnose` (`open` → `resolved`): all 4 concerns fixed in
  `130b720`, nits in `fe5ab5c`; Resolution footer attributes each. The one C4
  residual (un-caveated `/logout` in the canned Example) is fixed in this diff
  (`commands/diagnose-loop.md`).
- `v0.2.2-uv-tool-install-fix` (`open` → `closed`): both nits left as-is,
  defensible; Resolution footer + `_index` line.

### I2. Close the status-drift loop (signal #5)
- `commands/loop-bootstrap.md`: front-matter `status:` is the source of truth
  (not `_index` prose); drift check (b) flags stale-open reviews whose
  `commit_hash` trails HEAD → suggest `/review-review`; optional drift line in
  the output format.
- `commands/review-review.md`: new "## Closing the loop" section documents the
  three-layer lifecycle (same-commit → loop-bootstrap detection → review-review
  catch-up) and the `close_finding.py` revisit-trigger. Its write-back logic was
  already correct and is unchanged.

### I3. Validate + bump
- `.claude-plugin/plugin.json` 0.2.3 → 0.2.4.
- `claude plugin validate .` (B0 gate).

### I4. Review dispositions (`reviews/2026-05-30-v0.2.4-status-drift-closeout.md` — 0 blockers, 2 concerns, 2 nits)
- **CONCERN (N4 misattribution):** fixed — footer re-cited `fe5ab5c` → `130b720` (verified `fe5ab5c` never touched README).
- **CONCERN (`/review-review` enumerated from `_index`):** fixed — step 1 now globs `reviews/*.md` and reads front-matter, demoting `_index` to a derived view.
- **NIT (`_metrics.md` stale hypothesis):** fixed — superseded-marker added inline.
- **NIT (C3 quote):** rejected with evidence — phrase is verbatim at `setup-graphify.md:82`. Review flipped `open` → `closed` in-session (layer-1 discipline).

## Definition of done for v0.2.4

- [x] Phase D4 metrics computed → `reviews/_metrics.md`
- [x] `v0.2-setup-and-diagnose` reconciled `open` → `resolved` with attributed footer
- [x] `v0.2.2-uv-tool-install-fix` reconciled `open` → `closed` with footer
- [x] `_index.md` synced for both
- [x] C4 residual (Example `/logout`) fixed in `commands/diagnose-loop.md`
- [x] `/loop-bootstrap` uses front-matter as source of truth + flags stale-open
- [x] `/review-review` documents the three-layer lifecycle
- [x] `.claude-plugin/plugin.json` bumped to `0.2.4`
- [x] `claude plugin validate .` passes (B0 gate)
- [x] `/review` on the v0.2.4 diff: 2 concerns + 1 nit fixed in-session, 1 nit rejected with evidence — no unaddressed substantial findings (`reviews/2026-05-30-v0.2.4-status-drift-closeout.md`)
- [x] v0.2.4 tag created (annotated tag at `f3fd436`, pushed)

## Next session — PRD (2026-05-30)

- **Problem**: v0.2.4 is shipped (commit `f3fd436`, tag `v0.2.4` pushed), but two dogfood signals remain NO DATA — #1 (`/loop-bootstrap` on an empty project ≤4 lines) and #3 (`/tutor` diagnose-first) — and the D4 rollout decision (Chef2 Gemini / OOTA) is unblocked but not started.
- **Goal**: either (a) exercise signals #1/#3 — a fresh empty-project `/loop-bootstrap` (verify ≤4 lines) + one real `/tutor` run (verify diagnose-before-lecture), logging results to `reviews/_metrics.md`; or (b) begin rollout to Chef2 Gemini / OOTA.
- **Non-goal**: building `scripts/close_finding.py` (YAGNI; revisit only if hand-reconciling reviews gets error-prone); changing the `karpathy-reviewer.md` severity rubric (D4: leave it).
- **Decision**: rollout follows COMMIT_PLAN Phase D (D1 install + graphify baseline, D2 CLAUDE.md conflict check, D3 first review). Strict additions only — no edits to shipped v0.1/v0.2 commands.
- **Acceptance**: `reviews/_metrics.md` updated with signal #1/#3 observations (≤4-line bootstrap captured, tutor diagnose-first confirmed) OR a first rollout review landed in the target project's `reviews/` with `/loop-bootstrap` + `/review` run clean.

## Phase J — v0.3.0: review-gate hook (merge-to-master review floor)

The plugin's **first hook infrastructure** (no `hooks/` directory existed before).
A `PreToolUse` hook that surfaces when code lands on master without a fresh
review — the *systemic* counterpart to the tactical backfill-review of the
un-reviewed chief-of-staff money code. The backfill fixes the symptom; this hook
fixes the cause.

**Brief**
- **Problem:** the loop is fully manual — nothing *enforces* `/review`. During
  the 29–30 May sprint (master-collision + parallel sessions + time pressure)
  the heaviest, money-critical chief-of-staff code (matcher-SSOT `8195529`,
  triage-ledger `c111a9d`) reached master **unreviewed**. The loop fails exactly
  when it is needed most.
- **Goal:** a reusable, safe-by-default hook that surfaces/enforces that code
  changes have a fresh review in `reviews/` before they land on master — across
  every project that installs the loop.
- **Non-goal:** does not replace review *quality* (presence-check, not
  quality-check); does not catch diagnostic/operational mistakes (the 2026-05-30
  near-misses — wrong grep map, deploy timing — were not code bugs and a code
  gate would not catch them); does not gate per-commit; and does **not**
  intercept a `git merge`/`git push` typed directly in an external terminal — a
  `PreToolUse` hook only sees git commands Claude runs via the Bash tool.
  Terminal-side coverage would need an installed git `pre-merge-commit`/`pre-push`
  hook (deferred as future hardening, v0.3.x).
- **Decision:**
  1. **Gate on merge/push to master, not per-commit.** That is the convergence
     point where parallel sessions collide — exactly where 29–30 May went wrong.
     A per-commit hook coordinates no parallel sessions.
  2. **Warning-first + sanctioned, logged bypass.** Never silently hard-block
     (would get `--no-verify`'d or disabled). Bypass is allowed but
     visible + logged (`REVIEW_GATE_BYPASS=1`, recorded to the gate log).
  3. **Opt-in per project + configurable scope.** Plugin default = OFF (no
     config ⇒ silent). A project declares its own must-review globs and a mode
     in `.claude/review-gate.json`. A plugin hook that hard-blocks everywhere by
     default would be a disaster.
  4. **Presence-check, not quality-check.** The hook checks *that* a fresh review
     for the diff exists in `reviews/` (by `commit_hash`), not that it is good.
     A floor (zero→something), not a ceiling.
- **Acceptance:** in a test project, a merge-to-master touching a must-review
  path **without** a fresh review ⇒ warning (with logged-bypass option); paths
  outside scope ⇒ silent; manifest bumped (0.2.4 → 0.3.0); README section + a
  guide in `the-boris-cherny-way`; existing commands (`/review`,
  `/loop-bootstrap`, `/diagnose-loop`, …) keep working; `claude plugin validate
  .` passes.

> **Brief correction (verified against the manifest):** the brief said "now
> 0.2.1"; the shipped `plugin.json` is **0.2.4** (Phase I, tag `v0.2.4` pushed).
> New capability ⇒ minor bump to **0.3.0**, not a patch off 0.2.1.

### J1. New `hooks/` infrastructure
- `hooks/hooks.json` — `PreToolUse` with `matcher: "Bash"` → a single command
  hook: `bash "${CLAUDE_PLUGIN_ROOT}/hooks/review_gate.sh"`.

### J2. `hooks/review_gate.sh` — cross-platform launcher (fail-OPEN)
Buffers stdin and applies a cheap `case` pre-filter (`*git*merge*|*git*push*`) so
Python only starts for real candidates — no per-Bash-call cold-start tax on the
majority of commands. Then `cd` to its own directory (works with the backslash
path Claude passes on Windows — empirically verified in git-bash), resolve the
first of `python3 | python | py`, and run `review_gate.py` by **relative** name
(CWD-resolved — sidesteps msys↔Windows path impedance). If no Python is found,
`exit 0` — a broken gate must never block work.

### J3. `hooks/review_gate.py` — gate logic (Python stdlib only, no `jq`)
1. Read PreToolUse JSON from stdin; take `tool_input.command` and `cwd` (the
   project dir — *not* the launcher's CWD).
2. Best-effort detect a **master-landing git op**: `git merge <ref>` while on a
   master branch, or `git push … <master>` (explicit refspec or bare push from a
   master branch). Anything else ⇒ `exit 0` silently.
3. Load `<project>/.claude/review-gate.json`. Missing / `enabled:false` / empty
   `must_review` ⇒ `exit 0` silently (safe-by-default).
4. Compute landing files (`git diff --name-only` over the right range) and
   intersect with `must_review` globs. Empty intersection ⇒ `exit 0` silently
   (← "paths outside scope ⇒ silent").
5. Presence-check: scan `reviews/*.md` front-matter for a `commit_hash` matching
   the landing tip (tolerant short/long SHA prefix match). Found ⇒ `exit 0`
   silently (reviewed).
6. Otherwise **fire**: append a JSONL line to the gate log (always), then emit by
   mode — `warn` (systemMessage + exit 0, proceeds), `ask`
   (`permissionDecision: ask` — the visible, logged bypass point), or `block`
   (`permissionDecision: deny` + remediation + `REVIEW_GATE_BYPASS=1` escape).
   `REVIEW_GATE_BYPASS=1` short-circuits to allow in any mode, logged as a bypass.
   Any internal error ⇒ fail-OPEN.

### J4. Config schema + example
- `.claude/review-gate.json`: `{ enabled, mode, must_review[], master_branches[],
  reviews_dir, log_path }`. Defaults: `mode:"warn"`, `master_branches:["master",
  "main"]`, `reviews_dir:"reviews"`, `log_path:".claude/review-gate-log.jsonl"`.
- Ship a documented example (`hooks/review-gate.example.json`) using the
  chief-of-staff money paths with `mode:"ask"` (recommended for money-critical
  scope; the plugin *default* stays `warn` for least-surprise on first opt-in).

### J5. Tests — isolated, repeatable acceptance harness
- `tests/test_review_gate.py` (stdlib `unittest`, no deps): spins up a temp git
  repo (+ a bare origin for the push case) and drives `review_gate.py` as a
  subprocess. Asserts: (a) in-scope merge, no review ⇒ fires + log line;
  (b) out-of-scope path ⇒ silent; (c) in-scope **with** matching-`commit_hash`
  review ⇒ silent; (d) no config ⇒ silent; (e) `REVIEW_GATE_BYPASS=1` ⇒ allowed
  + logged bypass.

### J6. Validate + bump
- `claude plugin validate .` (B0 gate) — also confirms the new `hooks` wiring.
- `.claude-plugin/plugin.json` 0.2.4 → 0.3.0; add the `hooks` reference if the
  schema wants it (auto-discovery otherwise).

### J7. Docs
- `README.md`: a "Review gate" section — what it does, how to opt in, the config
  schema, the bypass, and the terminal-merge limitation.
- `the-boris-cherny-way/guides/review-gate.md`: the why (29–30 May post-mortem),
  the floor-not-ceiling framing, and the recommended money-path config.

### J8. Review + tag
- `/boris-karpathy-loop:review` on the v0.3.0 diff; address substantial findings.
- `git tag -a v0.3.0`.

## Definition of done for v0.3.0
- [x] `hooks/hooks.json` registers a `PreToolUse`/`Bash` command hook
- [x] `hooks/review_gate.sh` launcher: stdin pre-filter (no Python tax on non-merge/push Bash) + fail-open, cross-platform (verified on Win git-bash — fires `ask` + logs; skips `ls`/`git status`)
- [x] `hooks/review_gate.py`: detection + opt-in config + scope intersection + presence-check + warn/ask/block + logged bypass, fail-open on error
- [x] `.claude/review-gate.json` schema documented + `hooks/review-gate.example.json` shipped
- [x] `tests/test_review_gate.py` passes — 11 cases green (5 acceptance + 6 edge)
- [x] Out-of-scope paths verified silent; in-scope-no-review verified fires; bypass verified logged
- [x] `.claude-plugin/plugin.json` bumped to `0.3.0` (+ `hooks` key)
- [x] `claude plugin validate .` passes (B0 gate)
- [x] Existing commands unaffected (no edits to shipped command/agent/skill files)
- [x] README "Review gate" section + `the-boris-cherny-way/guides/review-gate.md` written
- [x] ruff check + ruff format + ty all clean on `hooks/` + `tests/`
- [x] `/review` on the v0.3.0 diff has no unaddressed substantial findings (`reviews/2026-06-01-v0.3.0-review-gate.md` — 0 blockers; 2 concerns + 2 nits all fixed in-session with regression tests; review `resolved`)
- [x] v0.3.0 tag created — local annotated tag `v0.3.0` at `c32f8f7` (push held pending real-session smoke test)

## Phase K — v0.3.1: review-gate Stop nudge (the orphan-review trigger)

Extends the v0.3.0 review-gate with a second, configurable trigger. Review is the
only step in brainstorm→plan→build→review with no automatic trigger: brainstorm/
plan/build happen in-session, but review hangs on a manual `/review` — even
`/wrap-session` has no review step. A `Stop` hook surfaces "you changed code
without a fresh review" while you can still act, closing that orphan gap.

**Brief**
- **Problem:** the review step is an orphan — nothing triggers it. The v0.3.0 gate
  only fires at merge/push, so committed-but-unreviewed code sits unflagged until
  (maybe) a merge much later — exactly the 29–30 May setup.
- **Goal:** a configurable Stop-hook nudge that surfaces, at turn-end, when HEAD
  carries must-review changes with no fresh review — soft, debounced, opt-in.
- **Non-goal:** does not block (soft `systemMessage` only); not `SessionEnd`
  (verified against the hooks docs: SessionEnd output is *ignored* — it can only
  log, never surface); not per-commit-on-master (consistent with the merge gate);
  does not replace the merge gate.
- **Decision:**
  1. **Stop, not SessionEnd.** SessionEnd cannot block or surface anything; Stop
     fires at every turn-end and *can* show a `systemMessage`. Stop is the only
     event that can nudge.
  2. **Signal = committed-but-unreviewed.** HEAD's branch-vs-master diff touches a
     `must_review` path AND no review's `commit_hash` matches HEAD. Reuses the
     merge gate's presence-check; ignores mid-edit dirt.
  3. **Debounced, soft, opt-in.** once-per-HEAD via
     `.claude/review-gate-state.json`; `systemMessage` only (never block); new
     config trigger `stop_nudge` (default OFF). `REVIEW_GATE_BYPASS=1` silences it.
  4. **No per-turn Python tax.** The launcher's `--stop` path exits in bash (file
     check → `grep` → one `git rev-parse`) and only spawns Python when HEAD is new.
- **Acceptance:** in a test project with `triggers.stop_nudge=true`, committing a
  `must_review` path on a feature branch without a review → next Stop emits a
  `systemMessage` nudge + writes state; running `/review` (stamps HEAD) → silent;
  out-of-scope commit → silent; `stop_nudge` absent/false → silent; second Stop on
  the same HEAD → silent (debounced). The `merge_push` trigger is unchanged when
  `triggers` is absent. manifest 0.3.0 → 0.3.1; README + guide updated; existing
  commands + the v0.3.0 merge gate keep working; `claude plugin validate .` passes.

### K1. Config — additive `triggers`
`.claude/review-gate.json` gains `"triggers": { "merge_push": true, "stop_nudge":
false }`. Absent ⇒ `merge_push` true, `stop_nudge` false (every v0.3.0 project
unchanged). `evaluate()` reads `triggers.merge_push` (default true);
`evaluate_stop()` requires `triggers.stop_nudge`.

### K2. `hooks/hooks.json` — add the Stop hook
A `Stop` entry → `bash "${CLAUDE_PLUGIN_ROOT}/hooks/review_gate.sh" --stop`.

### K3. `hooks/review_gate.sh` — `--stop` branch (cheap, fail-open)
If `--stop`: locate config via `$CLAUDE_PROJECT_DIR`; exit 0 if no config or no
`"stop_nudge": true` (grep). Else `git rev-parse HEAD`; if == `last_evaluated_head`
in `.claude/review-gate-state.json` → exit 0. Else buffer stdin and run
`python review_gate.py --stop`. The no-arg path (merge gate) is unchanged.

### K4. `hooks/review_gate.py` — `--stop` mode
`evaluate_stop(payload)`: resolve project; load config; require
`triggers.stop_nudge`; base = `merge-base(HEAD, <master>)` (fallback
`origin/<master>`); files = `diff base..HEAD`; intersect `must_review`; debounce on
`last_evaluated_head`; if hits AND no fresh review for HEAD AND not
`REVIEW_GATE_BYPASS` → soft `systemMessage`. Reuses `git`/`load_config`/
`must_review_hits`/`fresh_review_exists`. A simple `--stop` argv check selects
mode; the PreToolUse path is the default.

### K5. Tests + example + docs
- tests: nudge fires (committed `must_review` on a branch, no review); silent when
  HEAD reviewed; silent out-of-scope; silent when `stop_nudge` false; debounce
  (second eval same HEAD → state set, no nudge); merge-gate cases still green.
- `hooks/review-gate.example.json`: add the `triggers` block.
- README "Review gate" + the guide: document the Stop trigger, `triggers`, the
  state file, and `.gitignore` of state + log.

### K6. Validate + bump + review + tag
- `claude plugin validate .`; `plugin.json` 0.3.0 → 0.3.1.
- `/review` on the diff; reconcile; tag `v0.3.1` (local; push on user go-ahead).

## Definition of done for v0.3.1
- [x] `triggers` block (merge_push default true, stop_nudge default false), backward-compatible
- [x] `hooks/hooks.json` registers the `Stop` hook (`--stop`)
- [x] `review_gate.sh --stop`: config-grep + HEAD-debounce in bash; Python only on new HEAD; fail-open (Windows e2e: nudge fires, debounces, fast-silent when off)
- [x] `review_gate.py --stop`: committed-but-unreviewed detection, state I/O, soft `systemMessage`, bypass-aware
- [x] merge/push gate reads `triggers.merge_push`; unchanged when `triggers` absent (test_merge_gate_off_when_trigger_disabled + backward-compat verified)
- [x] tests cover fires / reviewed-silent / out-of-scope / not-enabled / debounce + fallback-base regression; full suite 22 green
- [x] ruff + ty clean
- [x] `.claude-plugin/plugin.json` 0.3.1; `claude plugin validate .` passes
- [x] README + guide updated (triggers, state file, gitignore)
- [x] existing commands + the v0.3.0 merge gate unaffected
- [x] `/review` on the v0.3.1 diff has no unaddressed substantial findings (`reviews/2026-06-01-v0.3.1-stop-nudge.md` — 0 blockers; 1 concern + 3 nits all fixed in-session; review `resolved`)
- [ ] v0.3.1 tag created (awaiting user go-ahead — following the v0.3.0 "commit + tag local" choice)

## Next session — PRD (2026-06-10): prove the gate fires + first opt-in

- **Problem**: the review-gate is built, committed/tagged, **installed (v0.3.1, user-scope cache)** and **verified loaded** in a fresh session — but it has **never been proven to actually FIRE** live, and **no project has opted in**, so "self-enforcing" is still effectively dark. (`/hooks`+`/plugin` are unavailable in this environment; "loaded" was confirmed via `claude plugin details`.)
- **Goal**: (a) prove the gate **fires** end-to-end in a fresh session, and (b) opt-in the first real project (chief-of-staff money paths) so it enforces for the first time.
- **Non-goal**: the v0.3.x git `pre-merge-commit`/`pre-push` variant (terminal-typed merges); pushing to GitHub (the local **Directory** marketplace means local install needs no push — push only for distribution); re-reviewing already-shipped gate code.
- **Decision**: verify via `claude plugin details boris-karpathy-loop@boris-karpathy-loop` (not `/hooks`). Fire-test = drop `.claude/review-gate.json` (`enabled:true, mode:"ask", must_review:[X], triggers:{stop_nudge:true}`) → change `X` on a branch → `git merge` to master → expect `⚠️ review-gate … NO fresh review` + a `.claude/review-gate-log.jsonl` line; negative control: out-of-scope path → silent. First opt-in target = chief-of-staff (`src/triage_ledger.py` + matching paths).
- **Acceptance**: a fresh session shows the gate **firing** on an in-scope merge (message + log line) and **silent** out-of-scope; chief-of-staff has a committed `.claude/review-gate.json`. (Optional: confirm `claude plugin details`'s "Agents (0)" is a harmless quirk by launching `/review`.)

### DoD-close (2026-06-11): PROVEN — both triggers observed live in a fresh session

- **Fire (merge gate, v0.3.0):** in-scope `git merge gate-fire-test` on `main` (test config `must_review: ["gate-probe/**"]`, mode `ask`) → ask-confirmation surfaced + log line: `{"ts": "2026-06-11T14:53:58", "event": "review-gate", "op": "merge", "tip_ref": "gate-fire-test", "branch": "main", "tip": "d4f31274", "must_review_hits": ["gate-probe/probe.txt"], "fresh_review": false, "mode": "ask", "decision": "ask", "bypassed": false}`.
- **Silent (negative control):** out-of-scope merge (`neg-probe.txt`) → no prompt, log unchanged (still 1 line).
- **Stop-nudge (v0.3.1):** fired at turn-end with the orphan `gate-probe` deliberately left on HEAD — log line: `{"ts": "2026-06-11T15:04:48", "event": "review-gate-nudge", "op": "stop", "tip": "1927ae9e", "must_review_hits": ["gate-probe/probe.txt"], "fresh_review": false, "decision": "nudge"}` + debounce state written (`last_evaluated_head` = `1927ae9e…`).
- **First opt-in:** chief-of-staff `f28c79f` on master — `mode: "ask"`, `stop_nudge: true`, `must_review` = `scripts/sync_onbetaalde_facturen.py` + `scripts/check_already_filed.py` + `src/triage_ledger.py`. NB: `src/matching/**` from the example config does **not** exist in chief-of-staff; the real 29–30 May incident files are `check_already_filed.py` + `triage_ledger.py` (verified via `git show --stat 8195529 c111a9d`). Log/state gitignored there.
- **Cleanup:** test merges reset away (`main` → `b600d79`), probe branches deleted, test config + debounce state removed; the gate log is retained locally as audit trail (gitignored).
- **Still open (v0.3.x backlog):** chef + project-2026 opt-ins; GitHub push when distribution is wanted; git `pre-merge-commit`/`pre-push` variant for terminal-typed merges. ("Agents (0)" quirk-check: **DONE 2026-06-11** — `/review` launched the karpathy-reviewer fine, 0/0/0 review of this very commit at `reviews/2026-06-11-dod-close-prd-fire-test.md`; the `claude plugin details` display is a harmless quirk.)

## Next session — PRD (2026-06-11): dogfood-signalen #1 & #3

- **Problem**: dogfood signals #1 (`/loop-bootstrap` on an empty project stays ≤4 lines) and #3 (`/tutor` diagnoses before lecturing) have been NO DATA since 2026-05-30 — two of five loop-quality signals are unmeasured while the plugin is now live-enforcing (chief-of-staff opt-in `f28c79f`).
- **Goal**: both signals measured and logged in `reviews/_metrics.md`: one fresh empty-project `/loop-bootstrap` run (count output lines, expect ≤4) + one real `/tutor` run (verify diagnose-before-lecture).
- **Non-goal**: chef + project-2026 gate-opt-ins (backlog — must_review scope per repo nog uit te zoeken; in chef matcht alleen `temp/chef2_ml_feedback.js` op "feedback"); building `/gate-optin` / `/gate-fire-drill` commands (analyze-session 2026-06-11 suggestion — signals first); the git pre-push hook variant.
- **Decision**: signal #1 runs in a throwaway empty dir with its own fresh session (loop-bootstrap reads cwd — running it from this repo is not representative); signal #3 piggybacks on the first genuine leervraag, not a forced artificial one.
- **Acceptance**: `reviews/_metrics.md` has two new observation lines (#1 with line count, #3 with diagnose-first yes/no), committed.

### Status (2026-06-11 wrap): #1 DONE, #3 pending

- **#1 measured PASS** — fresh headless session (`claude -p "/loop-bootstrap"`) in a throwaway empty dir: 3 non-empty lines (within the ≤4 band), logged in `reviews/_metrics.md`, commit `8f7fa16` (pushed).
- **#3 still pending** — event-driven per the Decision above; logs into `_metrics.md` at the first genuine leervraag. Does not block the next PRD.

## Next session — PRD (2026-06-11 wrap): chef + bonnetjes/2026 gate opt-ins

- **Problem**: the review-gate is proven but live in exactly one repo (chief-of-staff `f28c79f`); chef-generator-v2gemini and bonnetjes/2026 (originally drafted as "project-2026" — identified by Mich 2026-06-12 as `~/Dropbox/bonnetjes/2026`) still merge unreviewed changes to master, and their `must_review` scope is unverified (in chef only `temp/chef2_ml_feedback.js` matches "feedback" by name).
- **Goal**: both repos opted in — a committed `.claude/review-gate.json` (mode `ask`, `stop_nudge: true`) with a verified `must_review` list per repo, plus one fire-drill per repo (in-scope ask + out-of-scope silent) and cleanup.
- **Non-goal**: the git `pre-merge-commit`/`pre-push` hook variant; GitHub-marketplace distribution switch; changes to the plugin's `hooks/` code; building a `/gate-optin` command.
- **Decision**: derive `must_review` from real incident/money paths per repo (the chief-of-staff method: `git show --stat` on the incident commits), not from filename guesses; configs live and get committed in the target repos — only the DoD-close lands here.
- **Acceptance**: per repo a committed config + a logged gate-fire (`ask`) on an in-scope test merge + a silent out-of-scope negative control, testresten opgeruimd; one DoD-close line per repo appended under this PRD.

### DoD-close (2026-06-12): chef LIVE; bonnetjes/2026 bewust geen opt-in

- **chef-generator-v2gemini — LIVE** (`64ea63c` on main, pushed; chef's pre-commit suite ran green): `.claude/review-gate.json` with mode `ask`, `stop_nudge: true`, `must_review = task-queries.js + supabase.js + migrations/**` (incident method: `966f32c` include_deleted-outage hit task-queries.js; the 2026-06-12 testvervuiling saga hit the tasks data). `server.js` deliberately out of scope — 121KB god-file every feature touches; gating it would breed ask-fatigue → bypass culture. Log/state gitignored.
- **Fire-drill evidence (live, fresh headless session with cwd in chef):** in-scope probe merge (plumbing commit `d8321fc` touching task-queries.js, never landed) → ask surfaced + log line `{"ts": "2026-06-12T16:35:28", "event": "review-gate", "op": "merge", "branch": "main", "tip": "d8321fcd", "must_review_hits": ["task-queries.js"], "mode": "ask", "decision": "ask", "bypassed": false}`; headless cannot confirm an ask → merge denied → **zero mutation** (HEAD stayed `754b546`; chef's 14 pre-existing dirty WIP files untouched). Negative control: out-of-scope probe `9f3212b` (CLAUDE.md), script-level with chef cwd → silent, log unchanged. Drill design notes: probe commits built via git plumbing (`hash-object`/`read-tree`/`commit-tree`, temp index) so the working tree is never touched; no branches created; tmp files cleaned; unreferenced probe objects left for `git gc`.
- **bonnetjes/2026 — deliberate non-opt-in** (decision with Mich, 2026-06-12): no remote (push trigger can never fire), 0 merges in 80 commits (merge trigger dead), no `reviews/` convention (stop_nudge would nudge every docs-commit = noise). It is a branchless docs/data workspace; the money-code that *acts* on its data lives in chief-of-staff (gated `f28c79f`) and chef (gated `64ea63c`). Revisit only if bonnetjes ever grows its own scripts + a review convention.
- **Backlog after this close:** GitHub push (distribution) + git `pre-merge-commit`/`pre-push` variant. Gate rollout state: COS ✓ · chef ✓ · bonnetjes n/a (decided).
