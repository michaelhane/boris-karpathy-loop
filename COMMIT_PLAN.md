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

## Phase H — v0.2.3 (planned): post-commit graphify hook reliability

Surfaced during the v0.2.2 wrap: the post-commit hook fired with
`ignored null byte in input` and did **not** refresh `GRAPH_REPORT.md`
(it stayed at the previous commit until `graphify update .` was run by
hand). The auto-update is unreliable on Windows/Git-Bash.

- **Problem**: the graphify post-commit hook errors (`ignored null byte in input`) on Windows and leaves `GRAPH_REPORT.md` stale after a commit, so the graph silently drifts from HEAD until someone runs `graphify update .` manually.
- **Goal**: a post-commit hook that reliably refreshes `graph.json` + `GRAPH_REPORT.md` after each commit on Windows Git-Bash — or fails loudly instead of silently.
- **Non-goal**: rewriting graphify itself; changing hook behavior on macOS/Linux (only the Windows null-byte path is in scope).
- **Decision**: inspect `.git/hooks/post-commit` (~line 23); the null byte almost certainly comes from a command-substitution reading binary/CRLF `git` output — sanitize (`tr -d '\0'`) or change the capture. Keep it AST-only (`graphify update .`, no API cost).
- **Acceptance**: make a trivial commit on Windows; confirm `GRAPH_REPORT.md`'s "Built from commit" matches the new HEAD with no manual step and no `ignored null byte` warning.
