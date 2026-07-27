# Phase 2 Segmentation Roadmap Revision — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved design at `docs/superpowers/specs/2026-07-24-phase-2-segmentation-roadmap-revision-design.md` to the actual `docs/roadmap.md`, so the roadmap document itself (not just the design doc) reflects Talmo's segmentation-campaign findings, the real label inventory (#23), and the two related Phase-1 fixes.

**Architecture:** This is a single-file, ordered sequence of text edits to `docs/roadmap.md` on the existing branch `docs/phase-2-segmentation-roadmap-design` (PR #24 already open against `origin/main`). Each task is one self-contained edit (or tightly related pair of edits) verified by re-reading the changed region and checking it against the design doc, then committed. The final task does a whole-document consistency pass and updates the doc's own self-documenting revision log, per its established convention (see the existing dated entries at the bottom of the file).

**Tech Stack:** Markdown only. No code, no tests, no CI implications (`docs/**` is already in the CI path filter, but nothing here changes behavior).

## Global Constraints

- Single file: `c:\repos\sleap-roots-training-talmolab\docs\roadmap.md`.
- Branch: `docs/phase-2-segmentation-roadmap-design` (already checked out, already tracks `origin/docs/phase-2-segmentation-roadmap-design`, PR #24 already open). Do not create a new branch.
- Preserve the file's exact existing formatting conventions: `### Tier N — Title *(parenthetical)*` headings, `- **Bold label:** text` bullets, `**word**` emphasis style used throughout.
- Non-integer tier numbers (`4.5`, `6.5`, `6.7`) follow the precedent already set by `2.5`/`2.7` in this exact file — same heading style, same section shape (Deliverable/Oracle/Depends-on/Tracking bullets).
- Every substantive revision in this file has historically gotten a new dated entry in the "Roadmap review reconciliations" log at the bottom (see entries dated 2026-06-24 ×3, 2026-07-13, 2026-07-21). This revision must get one too, dated 2026-07-24.
- Source of truth for all new content: `docs/superpowers/specs/2026-07-24-phase-2-segmentation-roadmap-revision-design.md` (already present on this branch). Every task below quotes the exact text to insert — verify it against that spec file if anything looks ambiguous.
- Commit after every task (frequent commits, per the doc's own history of many small dated revisions). Push after each commit so PR #24 stays current.
- No task should touch: Phase boundary timing wording ("Open roadmap decisions" bullet 3), the `Tracking-issue policy` section's generic policy language, or Tier 9's content — these are explicitly unchanged per the design doc.

---

### Task 1: Amend Tier 3's compute-flexibility wording

**Files:**
- Modify: `docs/roadmap.md:205-211` (Tier 3 section)

**Interfaces:** N/A (doc-only task, no code interfaces).

- [ ] **Step 1: Make the edit**

Find this exact text (the Tier 3 deliverable bullet):

```markdown
### Tier 3 — Multi-dataset / generalist training + sweeps
- **Deliverable:** train a generalist model across ≥2 species **on the unified skeleton (Tier
  2.7)**; config-driven sweeps on Run:AI. **Draft the comparison matrix** (crops × root types)
  with Elizabeth to scope Tier 4.
```

Replace with:

```markdown
### Tier 3 — Multi-dataset / generalist training + sweeps
- **Deliverable:** train a generalist model across ≥2 species **on the unified skeleton (Tier
  2.7)**; config-driven sweeps **on Run:AI when available, or the A5000 workstation otherwise —
  compute location isn't prescribed, given Run:AI's sparse availability.** **Draft the comparison
  matrix** (crops × root types) with Elizabeth to scope Tier 4.
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "compute location isn't prescribed" docs/roadmap.md`
Expected: one match, inside the Tier 3 section (around line 207).

Run: `grep -c "config-driven sweeps on Run:AI\." docs/roadmap.md`
Expected: `0` (the old unqualified phrase should no longer exist as a standalone sentence — it's now the longer qualified version).

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): Tier 3 compute isn't Run:AI-exclusive"
git push
```

---

### Task 2: Insert new Tier 4.5 (production model selection)

**Files:**
- Modify: `docs/roadmap.md` — insert new section between Tier 4 (ends at line 223) and Tier 5 (starts at line 225).

**Interfaces:** N/A.

- [ ] **Step 1: Make the edit**

Find this exact text (end of Tier 4, start of Tier 5, with the blank line between them):

```markdown
- **Tracking:** Tier-4 EPIC. *(Co-owned harness — pair-programmed, see safeguards below.)*

### Tier 5 — Full labeling-QC tooling
```

Replace with (inserting the new Tier 4.5 section in between):

```markdown
- **Tracking:** Tier-4 EPIC. *(Co-owned harness — pair-programmed, see safeguards below.)*

### Tier 4.5 — Production model selection
- **Deliverable:** a documented, per-species decision — deploy the generalist, a species-specific
  specialist, or a generalist trained over some subset of species — backed by Tier 4's comparison
  table and trait-validation numbers. Explicitly allows "the generalist doesn't work for this
  species, use its specialist" as a valid, expected outcome, not an edge case. Reuses the existing
  publishing mechanism (`ModelCard`, `production` alias, `seed-registry` CLI) — no new registry
  surface.
- **Oracle:** every species in the drafted comparison matrix has a documented, evidence-backed
  production recommendation; recommendations are published to the registry via the existing
  mechanism.
- **Depends on:** Tier 4 (comparison table + trait validation is the evidence base).
- **Tracking:** Tier-4.5 EPIC. *(Same decision process repeats after Tier 9 for mask models —
  not its own tier number, just flag it when Tier 9 is reached.)*

### Tier 5 — Full labeling-QC tooling
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "^### Tier" docs/roadmap.md`
Expected output includes, in this exact order: `Tier 4`, `Tier 4.5`, `Tier 5`, `Tier 6`, ... (confirms correct insertion point and that no heading was duplicated or dropped).

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): add Tier 4.5 — production model selection"
git push
```

---

### Task 3: Rewrite Tier 6 (per-crop segmentation method bootstrapping)

**Files:**
- Modify: `docs/roadmap.md` — Tier 6 section (originally lines 233-238, line numbers will have shifted by +11 after Task 2's insertion — locate by heading text, not line number).

**Interfaces:** N/A.

- [ ] **Step 1: Make the edit**

Find this exact text:

```markdown
### Tier 6 — SAM-predict glue (poses → predicted masks)
- **Deliverable:** a pipeline step wrapping sleap-nn `run_sam_segmentation` to turn keypoint
  poses into `PredictedSegmentationMask` for review.
- **Oracle:** predicted masks on a sample (using keypoints from the unified skeleton, Tier 2.7)
  reach a mask-IoU threshold vs a hand-checked set.
- **Tracking:** Tier-6 EPIC. *(Re-verify sleap-nn mask state + pins at kickoff.)*
```

Replace with:

```markdown
### Tier 6 — Segmentation mask bootstrapping (per-crop method selection)
- **Deliverable:** for each crop/platform, empirically compare the available mask-generation
  methods rather than prescribing one:
  - **Zero-shot SAM** (optionally prompted with existing pose keypoints/bounding boxes)
  - **Talmo's pose-derived pseudo-mask heuristic** (fixed-width band around the skeleton — cheap,
    no training required, got decent results in his own experiments; documented in
    `sleap-nn`'s `scratch/2026-07-05-plant-seg-experiments/analysis/E_synthesis/FINDINGS.md` and
    `.../analysis/gt_ceiling/README.md`)
  - **Real hand-labeled masks**, where #23's inventory already has them (cylinder Arabidopsis;
    smaller rice/sorghum/soybean batches)

  Pick (and document) whichever produces usable, review-ready masks for that crop's actual
  morphology — mirrors this roadmap's existing "establish then reproduce-or-beat" oracle
  philosophy rather than assuming one method wins everywhere.
- **Oracle:** a per-crop comparison table (method vs. mask-IoU/clDice against a small hand-checked
  reference set) with a documented decision per crop.
- **Depends on:** #23 (need the real-label inventory to know which crops get a "real labels" arm).
- **Compute note:** doesn't require Run:AI specifically — may run on the A5000 workstation, same
  as Tier 7.
- **Tracking:** Tier-6 EPIC. *(Re-verify sleap-nn mask state + pins at kickoff.)*
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "per-crop method selection" docs/roadmap.md`
Expected: one match, in the Tier 6 heading.

Run: `grep -n "SAM-predict glue" docs/roadmap.md`
Expected: no matches (the old framing/title text is fully replaced) — if this returns a match, check whether it's in the "Roadmap review reconciliations" historical log (append-only, must NOT be edited) rather than the live Tier 6 section; only the live section's occurrence should be gone.

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): Tier 6 reframed as per-crop segmentation method comparison"
git push
```

---

### Task 4: Insert new Tier 6.5 and Tier 6.7

**Files:**
- Modify: `docs/roadmap.md` — insert two new sections between the (now-rewritten) Tier 6 and Tier 7.

**Interfaces:**
- Consumes: Tier 6's per-crop candidate masks (referenced by name, no code interface).
- Produces: corrected labels that Tier 7 (Task 5) references as its training input.

- [ ] **Step 1: Make the edit**

Find this exact text (end of Tier 6 from Task 3, start of the original Tier 7 heading):

```markdown
- **Tracking:** Tier-6 EPIC. *(Re-verify sleap-nn mask state + pins at kickoff.)*

### Tier 7 — Pipeline mask training
```

Replace with (inserting both new sections):

```markdown
- **Tracking:** Tier-6 EPIC. *(Re-verify sleap-nn mask state + pins at kickoff.)*

### Tier 6.5 — Standalone segmentation correction GUI
- **Deliverable:** build out a review/correction tool — extending the `vibes.tlab.sh` prototypes
  (`sam3-segmenter`, `labelroi`), built on `sleap-io.js` — that lets someone load candidate masks
  (from whichever Tier 6 method won for a crop) and correct them into real training labels,
  round-tripping to `.slp`. Real, buildable-now roadmap content, no cross-repo dependency.
- **Oracle:** a reviewer can load Tier 6's candidate masks for a crop, correct/accept/reject them,
  and export a valid `.slp` with corrected masks — usable standalone.
- **Depends on:** Tier 6 (needs candidate masks to correct against).
- **Feeds:** Tier 7 (corrected masks become real training labels).
- **Tracking:** Tier-6.5 EPIC. *(Good early pairing opportunity — engineering-track person builds
  the tool, modeling-track person is the first real reviewer/user.)*
- **Relationship to Tier 8:** Tier 8 is repurposed to be the later "upstream this into `sleap-app`"
  migration — this tier is what actually gets labels reviewed now.

### Tier 6.7 — Segmentation labeling strategy + coverage plan
- **Deliverable:** per-crop assessment of whether #23's existing label inventory is sufficient for
  Tier 7 training, or whether more labels are needed — plus a minimal QC checklist for
  segmentation masks (mask-specific analog of Tier 2.5's pose checklist: no holes/disconnected
  fragments, tight boundaries, sane foreground/background balance). Where more labels are needed,
  Tier 6.5's correction GUI is the tool used to produce them.
- **Oracle:** seed QC flags a planted set of known mask errors (mirrors Tier 2.5's oracle); a
  documented per-crop verdict ("enough data" / "needs N more labeled frames") before Tier 7 sweeps
  begin.
- **Depends on:** Tier 6 (need the per-crop method comparison first), Tier 6.5 (the tool that
  would produce more labels if needed).
- **Tracking:** Tier-6.7 EPIC.

### Tier 7 — Pipeline mask training
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "^### Tier" docs/roadmap.md`
Expected order includes: `Tier 6`, `Tier 6.5`, `Tier 6.7`, `Tier 7`, `Tier 8`, `Tier 9` — no duplicates, no gaps.

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): add Tier 6.5 (correction GUI) and Tier 6.7 (labeling strategy)"
git push
```

---

### Task 5: Rewrite Tier 7 (validated recipe, sweep clause, compute note, concrete starting point)

**Files:**
- Modify: `docs/roadmap.md` — Tier 7 section (originally lines 240-247).

**Interfaces:**
- Consumes: Tier 6.5's corrected labels (referenced by name).

- [ ] **Step 1: Make the edit**

Find this exact text:

```markdown
### Tier 7 — Pipeline mask training
- **Deliverable:** train `bottomup_segmentation` / `centered_instance_segmentation` via the
  pipeline; config-driven.
- **Oracle:** mask model meets a mask-AP/IoU target on held-out data.
- **Tracking:** Tier-7 EPIC. *(Splits into a "runs it" role and a "builds the tooling" role.)*
- **Not blocked by Tier 8:** mask corrections for training can be done programmatically
  (`sleap-io` `PredictedSegmentationMask.to_user()`) or via the desktop path in the interim. The
  web GUI (Tier 8) is a quality-of-life accelerator, **not** a critical-path dependency.
```

Replace with:

```markdown
### Tier 7 — Pipeline mask training
- **Deliverable:** train `bottomup_segmentation`/`centered_instance_segmentation` (or whole-frame
  semantic, per Tier 6's per-crop decision) via the config-driven pipeline from Tier 1, starting
  from Talmo's validated recipe as the default rather than an open hyperparameter search:
  whole-frame UNet, output-stride 4, BCE/Dice 0.5/0.5, no `pos_weight`; tiling only when a crop's
  objects are smaller than the tile (compact/lateral roots — never elongated primaries); top-down
  instance segmentation for compact-root crops (bottom-up is not yet deployable as-is per the
  campaign's audit — mislabels/misses roughly half even after the grouping-field retrain).
- **Sweep clause (parity with Tier 3's pose sweeps):** for crops where Talmo's campaign already
  validated the recipe on that exact crop (e.g. cylinder Arabidopsis — SAM3 zero-shot clDice
  0.808 vs. trained UNet clDice 0.866, n=17), reuse it directly. For crops it didn't cover, or
  where the audit flagged single-seed/single-crop scope (most results are soy_lateral-only), run a
  light confirmatory config-driven sweep (backbone, output-stride, tile size) before committing —
  do not assume the borrowed recipe transfers untested.
- **Concrete starting point:** for cylinder Arabidopsis specifically, packaged train/val
  `.pkg.slp` files already exist from Talmo's campaign
  (`sleap-nn`'s `scratch/2026-07-05-plant-seg-experiments/data/masks/cyl_arabidopsis_foreground*.pkg.slp`,
  `cyl_arabidopsis_instance*.pkg.slp`) — use directly rather than regenerating, same spirit as
  reusing the Tier 1 keypoint split files.
- **Oracle:** mask model meets a mask-AP/IoU target on held-out data, established the same way
  Tier 1 established its keypoint baseline — report the new model's own range next to the
  campaign's reference numbers as context, not a pass/fail gate.
- **Compute note:** doesn't require Run:AI specifically — may run on the A5000 workstation.
- **Tracking:** Tier-7 EPIC. *(Splits into a "runs it" role and a "builds the tooling" role.)*
- **Not blocked by Tier 8:** mask corrections for training can be done via Tier 6.5's standalone
  tool now, or programmatically (`sleap-io` `PredictedSegmentationMask.to_user()`) in the
  interim. Tier 8 (upstreaming into `sleap-app`) is a later migration, **not** a critical-path
  dependency.
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "clDice 0.866" docs/roadmap.md`
Expected: one match, inside the Tier 7 section.

Run: `grep -n "PredictedSegmentationMask.to_user" docs/roadmap.md`
Expected: one match (confirms the "not blocked by Tier 8" bullet survived the rewrite, just amended).

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): Tier 7 starts from Talmo's validated recipe + sweep clause"
git push
```

---

### Task 6: Rewrite Tier 8 (repurpose to later sleap-app upstream)

**Files:**
- Modify: `docs/roadmap.md` — Tier 8 section (originally lines 249-254).

**Interfaces:** N/A.

- [ ] **Step 1: Make the edit**

Find this exact text:

```markdown
### Tier 8 — Mask review/correct GUI in `sleap-app` (talmolab/sleap-app#155 Phase-1) *(cross-repo, off critical path)*
- **Deliverable:** render + accept/reject predicted masks in the web app, round-tripping `.slp`.
- **Oracle:** a reviewer can load predicted masks, accept/reject, and re-save valid `.slp`;
  accepted by SLEAP-team review.
- **Tracking:** ties to existing talmolab/sleap-app#155; cross-repo with the SLEAP team; buy-in secured
  in Tier 0.5; **draft the sub-issue set and get SLEAP-team go-ahead before filing in their repo.**
```

Replace with:

```markdown
### Tier 8 — Upstream the correction tool into `sleap-app` (talmolab/sleap-app#155 Phase-1) *(cross-repo, off critical path)*
- **Deliverable:** migrate/rebuild Tier 6.5's standalone correction tool as native `sleap-app`
  functionality, round-tripping `.slp`. Repurposed from the original framing — Tier 6.5 already
  provides the actual review path; this is the later "make it a first-class part of the shared
  app" step.
- **Oracle:** a reviewer can load predicted masks in `sleap-app`, accept/reject, and re-save valid
  `.slp`; accepted by SLEAP-team review.
- **Tracking:** ties to existing talmolab/sleap-app#155; cross-repo with the SLEAP team; buy-in secured
  in Tier 0.5; **draft the sub-issue set and get SLEAP-team go-ahead before filing in their repo.**
  **Genuinely off critical path now**, since Tier 6.5 already unblocks real review/correction work
  without it.
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "Upstream the correction tool" docs/roadmap.md`
Expected: one match, in the Tier 8 heading.

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): Tier 8 repurposed to later sleap-app upstream, off critical path"
git push
```

---

### Task 7: Add the Phase 3 parked joint pose+segmentation model idea

**Files:**
- Modify: `docs/roadmap.md` — Phase 3 section (originally lines 262-268).

**Interfaces:** N/A.

- [ ] **Step 1: Make the edit**

Find this exact text:

```markdown
## Phase 3 — Future extension (parked, not scheduled)

- **Self-hosted labeling platform (our data only)** on `sleap-app`, with **W&B registry
  integration** (push/pull `sleap-roots-labels`), compute via LabLink. Gated on talmolab/sleap-app#155 maturing +
  SLEAP-team coordination. Tracked as a separate program when reached.
- **(Possible)** downstream deployment of the finished models into the `sleap-roots` phenotyping
  pipeline — out of scope here; revisit if/when the models are production-bound.
```

Replace with:

```markdown
## Phase 3 — Future extension (parked, not scheduled)

- **Self-hosted labeling platform (our data only)** on `sleap-app`, with **W&B registry
  integration** (push/pull `sleap-roots-labels`), compute via LabLink. Gated on talmolab/sleap-app#155 maturing +
  SLEAP-team coordination. Tracked as a separate program when reached.
- **(Possible)** downstream deployment of the finished models into the `sleap-roots` phenotyping
  pipeline — out of scope here; revisit if/when the models are production-bound.
- **(Possible)** a single model outputting both pose and segmentation masks from a shared
  backbone (Mask-R-CNN-style multi-task head). **Not currently possible**: `sleap_nn`'s
  `HeadConfig` (`sleap_nn/config/model_config.py`) is `@oneof`-constrained to exactly one head
  type per model, across all nine head types (`single_instance`, `centroid`, `centered_instance`,
  `bottomup`, two multi-class variants, `bottomup_segmentation`,
  `centered_instance_segmentation`, `semantic_segmentation`). Would require new upstream
  `sleap-nn` capability — a combined head type or relaxing the `@oneof` constraint — not
  achievable from this repo's config layer alone.
```

- [ ] **Step 2: Verify the edit**

Run: `grep -n "Mask-R-CNN-style" docs/roadmap.md`
Expected: one match, in the Phase 3 section.

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): park the joint pose+segmentation model idea in Phase 3"
git push
```

---

### Task 8: Fix cross-references in "Work tracks" that name Tier 6/8 by their old roles

**Files:**
- Modify: `docs/roadmap.md:57` and `docs/roadmap.md:63-64` (original line numbers — locate by text, they will have shifted).

**Interfaces:** N/A.

**Why this task exists:** the "Work tracks" section was written when Tier 8 was the only review/correct GUI and Tier 6 was pure SAM-glue. Both references are now stale relative to the rewritten tiers.

- [ ] **Step 1: Make the first edit**

Find this exact text:

```markdown
- **Engineering track:** pipeline architecture + tooling; the mask-review GUI (Tier 8).
```

Replace with:

```markdown
- **Engineering track:** pipeline architecture + tooling; the mask-review GUI (Tier 6.5, later
  upstreamed to `sleap-app` in Tier 8).
```

- [ ] **Step 2: Make the second edit**

Find this exact text:

```markdown
- **Co-owned seams:** the evaluation/comparison harness (Tier 4) and the SAM-predict →
  review/correct loop (Tiers 6 + 8).
```

Replace with:

```markdown
- **Co-owned seams:** the evaluation/comparison harness (Tier 4) and the segmentation
  bootstrap → review/correct loop (Tiers 6 + 6.5).
```

- [ ] **Step 3: Verify both edits**

Run: `grep -n "Tier 6.5, later" docs/roadmap.md`
Expected: one match.

Run: `grep -n "bootstrap → review/correct loop" docs/roadmap.md`
Expected: one match.

Run: `grep -n "SAM-predict →" docs/roadmap.md`
Expected: no matches in the live "Work tracks" section (only, if any, inside the append-only historical revision log further down — do not touch those).

- [ ] **Step 4: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): fix Work-tracks cross-references to Tier 6.5/8"
git push
```

---

### Task 9: Update the header date and append the dated revision-log entry

**Files:**
- Modify: `docs/roadmap.md:4` (Last revised date)
- Modify: `docs/roadmap.md` — end of file, after the 2026-07-21 entry (append-only; do not edit prior entries).

**Interfaces:** N/A.

**Why this task exists:** every prior substantive revision to this file got a dated header bump and a new entry in "Roadmap review reconciliations." This revision needs the same, per the doc's own established convention (verified above during Task 3's verify step — the historical log is append-only, never edited in place).

- [ ] **Step 1: Update the header date**

Find this exact text:

```markdown
**Last revised:** 2026-07-21 (see the dated revision log at the bottom for what changed and why).
```

Replace with:

```markdown
**Last revised:** 2026-07-24 (see the dated revision log at the bottom for what changed and why).
```

(If the file already shows a different "Last revised" date than 2026-07-21 at this point — e.g. because a different PR merged in the meantime — update whatever date is currently there to 2026-07-24 instead; don't assume 2026-07-21 is still current without checking first with `grep -n "Last revised" docs/roadmap.md`.)

- [ ] **Step 2: Append the new revision-log entry**

Find the exact last two lines of the file (the end of the 2026-07-21 entry):

```markdown
- **MINOR:** Tier 0.5 is **not** marked "done" here — completion is tracked by #9 + the CHANGELOG
  per the JIT tracking policy; this entry only corrects now-false forward-looking facts.
```

Append immediately after (do not modify the text above; this is a pure addition at end-of-file):

```markdown

**Roadmap revision (2026-07-24)** — Phase 2 rebuilt on Talmo's segmentation campaign + the real
label inventory; two related Phase-1 fixes folded in.
- **IMPORTANT (Phase 2 completeness):** **Tier 6 reframed** from a single prescribed method
  ("SAM-predict glue") to a per-crop empirical comparison (SAM / Talmo's pose-derived pseudo-mask
  heuristic / real labels per #23), matching the oracle philosophy already used elsewhere in this
  document rather than assuming one method transfers universally.
- **IMPORTANT (Phase 2 completeness):** **Tier 6.5 added** (standalone segmentation correction
  GUI, built on the `vibes.tlab.sh` prototypes + `sleap-io.js`) so mask review/correction is real,
  buildable-now work — not gated on `sleap-app`/SLEAP-team coordination the way the original
  Tier 8 framing required. **Tier 8 repurposed** accordingly: it's now the later "upstream into
  `sleap-app`" migration, genuinely off critical path since Tier 6.5 already unblocks review.
- **IMPORTANT (Phase 2 completeness):** **Tier 6.7 added** (segmentation labeling strategy +
  coverage/QC plan) — Tier 2.5 asked this question for pose labels before Tier 3's sweeps; nothing
  analogous existed for segmentation before Tier 7's training.
- **IMPORTANT (oracle grounding):** **Tier 7 now starts from Talmo's validated recipe**
  (whole-frame UNet, output-stride 4, BCE/Dice 0.5/0.5, no `pos_weight`; tiling only for
  small-object crops; top-down instance seg for compact roots) as its default, with a sweep clause
  for crops the campaign didn't cover or where its own 2026-07-08 audit flagged single-seed/
  single-crop scope — parity with Tier 3's existing sweep treatment for pose, rather than
  assuming a borrowed recipe transfers untested. Concrete packaged `.pkg.slp` starting point for
  cylinder Arabidopsis noted directly.
- **IMPORTANT (completeness, Phase 1):** **Tier 4.5 added** (production model selection) — Tier 4
  produced a generalist-vs-specialist comparison table, but nothing described the actual decision
  process for choosing what ships to production per species, including "the generalist doesn't
  work for this species" as a valid outcome. Reuses the existing `ModelCard`/`production`-alias
  publishing mechanism.
- **MINOR (compute realism):** **Tier 3 and Tier 7 no longer assume Run:AI exclusively** — both
  now allow the A5000 workstation, given Run:AI's sparse availability.
- **MINOR:** **Work tracks cross-references fixed** — the engineering-track and co-owned-seams
  bullets named Tier 8 as the mask-review GUI and "Tiers 6 + 8" as the SAM-predict loop; both are
  stale relative to the Tier 6/6.5/8 rewrite above and are corrected here.
- **MINOR (parked idea):** **Phase 3 gained a joint pose+segmentation model entry** — not
  currently possible given `sleap_nn`'s `@oneof`-constrained `HeadConfig` (verified directly
  against `sleap_nn/config/model_config.py`); recorded as a future idea, not scheduled.
- Design doc: `docs/superpowers/specs/2026-07-24-phase-2-segmentation-roadmap-revision-design.md`.
```

- [ ] **Step 3: Verify**

Run: `grep -n "Last revised:\*\* 2026-07-24" docs/roadmap.md`
Expected: one match, near the top of the file.

Run: `tail -20 docs/roadmap.md`
Expected: the new 2026-07-24 entry is the last thing in the file, the 2026-07-21 entry above it is unchanged.

- [ ] **Step 4: Commit**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): bump last-revised date, log the 2026-07-24 Phase 2 revision"
git push
```

---

### Task 10: Whole-document consistency pass

**Files:**
- Read (no modification expected unless an inconsistency is found): `docs/roadmap.md` in full.

**Interfaces:** N/A.

**Why this task exists:** verify the cumulative effect of Tasks 1-9 didn't introduce a structural or cross-reference problem the per-task verifications wouldn't individually catch.

- [ ] **Step 1: Re-read the full file**

Run: `grep -n "^#\|^##\|^###" docs/roadmap.md`
Expected: a clean heading outline, in order: `# Generalist SLEAP Root Models`, `## Oracle / validation philosophy`, `## Upstream version pins`, `## Work tracks`, `## Adjacent work`, `## Tier 0`, `## Tier 0.5`, `## Phase 1`, `### Tier 1` ... `### Tier 5`, `## Phase 2`, `### Tier 6`, `### Tier 6.5`, `### Tier 6.7`, `### Tier 7`, `### Tier 8`, `### Tier 9`, `## Phase 3`, `## Execution cadence & safeguards`, `## Tracking-issue policy`, `## Open roadmap decisions`, `## Roadmap review reconciliations`.

- [ ] **Step 2: Check for any remaining stale tier-number cross-references**

Run: `grep -n "Tier 6 + 8\|Tiers 6 and 8\|Tier 8).\|(Tier 8)" docs/roadmap.md`
Read every match. Confirm each surviving occurrence is either (a) inside the append-only historical log, or (b) a live, intentionally-still-correct reference (e.g. Tier 0.5's `talmolab/sleap-app#155` buy-in bullet, which legitimately still names Tier 8 as the fallback if buy-in fails — that one is correct as-is and should NOT be changed). If any live, non-historical, factually-wrong reference to Tier 8's old role turns up, fix it and note the fix as an addendum to the 2026-07-24 revision-log entry from Task 9.

- [ ] **Step 3: Confirm the "Open roadmap decisions" and "Tracking-issue policy" sections were correctly left untouched**

Run: `git diff origin/main -- docs/roadmap.md | grep -A3 "Open roadmap decisions"`
Expected: no diff hunk touches this section (confirms Task-1-through-9 edits stayed out of it, per the Global Constraints).

- [ ] **Step 4: Final full-file review**

Read the complete file top to bottom once. Confirm: no markdown syntax errors (unclosed bold/italic, mismatched heading levels), no leftover placeholder text, the Phase 2 tier sequence reads coherently end-to-end (6 → 6.5 → 6.7 → 7 → 8 → 9).

- [ ] **Step 5: If any fix was needed in Steps 2-4, commit it**

```bash
git add docs/roadmap.md
git commit -m "docs(roadmap): consistency-pass fixes"
git push
```

If no fix was needed, this task produces no commit — that's fine, it's a verification task.

---

## Self-Review Notes (completed during plan writing)

- **Spec coverage:** every section of the design doc (Tier 3 amendment, Tier 4.5, Tier 6 rewrite, Tier 6.5, Tier 6.7, Tier 7 rewrite, Tier 8 rewrite, Tier 9 unchanged, Phase 3 addition) maps to Tasks 1, 2, 3, 4, 4, 5, 6, *(no task — confirmed unchanged in Task 10)*, 7 respectively. Tasks 8-9 (cross-reference fixes, revision log) were not in the design doc's explicit section list but are required by the design doc's own "Out of scope" note that this is a doc-only edit needing internal consistency — added here as the concrete mechanism for that.
- **Placeholder scan:** no "TBD"/"TODO" in any task; every `old_string`/`new_string` pair is complete, copy-pasteable text.
- **Type consistency:** N/A (no code types); tier names/numbers are used consistently across tasks (`Tier 6.5`, `Tier 6.7`, `Tier 4.5` spelled identically everywhere they appear).
