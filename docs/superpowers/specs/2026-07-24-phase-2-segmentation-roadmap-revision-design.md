# Roadmap revision: Phase 2 segmentation tiers + related Phase 1/3 amendments

**Date:** 2026-07-24
**Status:** Design — not yet applied to `docs/roadmap.md`
**Scope:** Revise Phase 2 (Tiers 6-9) to reflect new findings; two related amendments to Phase 1
(Tier 3, and a new Tier 4.5); one Phase 3 addition (parked idea).

## Why this revision

The current `docs/roadmap.md` Phase 2 section (Tiers 6-9) was written before three things were
known:

1. **Talmo's audited plant-segmentation experiment campaign**
   (`V:\talmo\sleap-nn\scratch\2026-07-05-plant-seg-experiments`) — a real, self-corrected body of
   work with validated recipes across 8 species/root-type datasets, including cylinder Arabidopsis
   specifically. Key docs: `analysis/CAMPAIGN_FINDINGS.md` (TL;DR) and `analysis/REPORT/report.md`
   (the audited, corrected final version — trust this over the findings doc where they disagree).
2. **A real segmentation-label inventory** already exists (tracked in
   `talmolab/sleap-roots-training#23`): 42 Arabidopsis cylinder images across 3 batches (16/16/10,
   differing lighting/crop conditions), plus smaller rice/sorghum/soybean cylinder batches — none
   of it registered in `sleap-roots-labels` yet.
3. **The mask-capable `sleap-nn`/`sleap-io` releases are already tagged** (v0.3.0 / 0.8.0+),
   removing the commit-pin blocker Phase 2 was originally written to wait on.

This design revises Phase 2's tier content to build on all three, rather than starting Phase 2
from the original, now-outdated framing. Two Phase 1 items surfaced during the same discussion are
included since they're directly related (a compute-flexibility note, and a real gap: no tier
currently describes the actual production-model-selection decision process). One Phase 3 "parked"
idea (joint pose+segmentation model) is added for the record, not scheduled.

## Revised Tier 3 (Phase 1) — compute-flexibility amendment only

No content changes beyond the compute assumption. Current text says sweeps run "on Run:AI"; amend
to:

> config-driven sweeps **on Run:AI when available, or the A5000 workstation otherwise — compute
> location isn't prescribed, given Run:AI's sparse availability.**

## New Tier 4.5 (Phase 1) — Production model selection

**Gap this closes:** Tier 4 produces a generalist-vs-specialist comparison table + trait
validation. The "Adjacent work" section documents the *publishing mechanism* (`ModelCard`,
`production` alias, `seed-registry` CLI). Nothing currently describes the actual **decision
process** for choosing, per species, what goes to production.

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
- **Tracking:** Tier-4.5 EPIC.
- **Note:** the same decision process should be repeated after Tier 9 (mask generalist-vs-
  specialist comparison) when that lands — not spelled out as its own tier number here, just flag
  it when Tier 9 is reached.

## Revised Tier 6 — Segmentation mask bootstrapping (per-crop method selection)

Replaces the current "SAM-predict glue" framing (which assumed no labels exist and prescribed one
method universally) with an empirical, per-crop comparison.

- **Deliverable:** for each crop/platform, empirically compare the available mask-generation
  methods rather than prescribing one:
  - **Zero-shot SAM** (optionally prompted with existing pose keypoints/bounding boxes)
  - **Talmo's pose-derived pseudo-mask heuristic** (fixed-width band around the skeleton — cheap,
    no training required, got decent results in his own experiments; documented in
    `analysis/E_synthesis/FINDINGS.md` and `analysis/gt_ceiling/README.md`)
  - **Real hand-labeled masks**, where #23's inventory already has them (cylinder Arabidopsis;
    smaller rice/sorghum/soybean batches)

  Pick (and document) whichever produces usable, review-ready masks for that crop's actual
  morphology — mirrors the project's existing "establish then reproduce-or-beat" oracle
  philosophy rather than assuming one method wins everywhere.
- **Oracle:** a per-crop comparison table (method vs. mask-IoU/clDice against a small hand-checked
  reference set) with a documented decision per crop.
- **Depends on:** #23 (need the real-label inventory to know which crops get a "real labels" arm).
- **Compute note:** doesn't require Run:AI specifically — may run on the A5000 workstation, same
  as Tier 7 below.
- **Tracking:** Tier-6 EPIC (re-verify `sleap-nn` mask-capable release pins at kickoff, per the
  existing convention).

## New Tier 6.5 — Standalone segmentation correction GUI

**Gap this closes:** the original Tier 8 bundled "build a review GUI" with "do it inside
`sleap-app`, gated on SLEAP-team buy-in" — meaning no review tooling existed until that cross-repo
coordination landed. The `vibes.tlab.sh` prototypes (`sam3-segmenter`, `labelroi`) already show
this is buildable now, independent of `sleap-app`.

- **Deliverable:** build out a review/correction tool — extending the `vibes.tlab.sh` prototypes,
  built on `sleap-io.js` — that lets someone load candidate masks (from whichever Tier 6 method won
  for a crop) and correct them into real training labels, round-tripping to `.slp`. Real,
  buildable-now roadmap content, no cross-repo dependency.
- **Oracle:** a reviewer can load Tier 6's candidate masks for a crop, correct/accept/reject them,
  and export a valid `.slp` with corrected masks — usable standalone.
- **Depends on:** Tier 6 (needs candidate masks to correct against).
- **Feeds:** Tier 7 (corrected masks become real training labels).
- **Tracking:** Tier-6.5 EPIC. *(Good early pairing opportunity — engineering-track person builds
  the tool, modeling-track person is the first real reviewer/user.)*
- **Relationship to Tier 8:** Tier 8 (below) is repurposed to be the later "upstream this into
  `sleap-app`" migration — this tier is what actually gets labels reviewed now.

## New Tier 6.7 — Segmentation labeling strategy + coverage plan

**Gap this closes:** Tier 2.5 (pose) asks "is our labeling strategy/coverage sufficient, with what
QC?" before Tier 3 sweeps. Nothing analogous existed for segmentation before Tier 7 training.

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

## Revised Tier 7 — Pipeline mask training

- **Deliverable:** train `bottomup_segmentation`/`centered_instance_segmentation` (or whole-frame
  semantic, per Tier 6's per-crop decision) via the config-driven pipeline from Tier 1, starting
  from Talmo's validated recipe as the default rather than an open hyperparameter search:
  whole-frame UNet, output-stride 4, BCE/Dice 0.5/0.5, no `pos_weight`; tiling only when a crop's
  objects are smaller than the tile (compact/lateral roots — never elongated primaries); top-down
  instance segmentation for compact-root crops (bottom-up is not yet deployable as-is per the
  campaign's audit — mislabels/misses roughly half even after the grouping-field retrain).
- **Sweep clause (parity with Tier 3's pose sweeps):** for crops where Talmo's campaign already
  validated the recipe on that exact crop (e.g. cylinder Arabidopsis — SAM3 zero-shot clDice
  0.808 vs. trained UNet clDice 0.866, n=17 per `analysis/E_synthesis/master.csv`), reuse it
  directly. For crops it didn't cover, or where the audit flagged single-seed/single-crop scope
  (most results are soy_lateral-only), run a light confirmatory config-driven sweep (backbone,
  output-stride, tile size) before committing — do not assume the borrowed recipe transfers
  untested.
- **Oracle:** mask model meets a mask-AP/IoU target on held-out data, established the same way
  Tier 1 established its keypoint baseline — report the new model's own range next to the
  campaign's reference numbers as context, not a pass/fail gate.
- **Concrete starting point:** for cylinder Arabidopsis specifically, packaged train/val
  `.pkg.slp` files already exist from Talmo's campaign
  (`data/masks/cyl_arabidopsis_foreground*.pkg.slp`, `cyl_arabidopsis_instance*.pkg.slp`) — use
  directly rather than regenerating, same spirit as reusing the Tier 1 keypoint split files.
- **Compute note:** doesn't require Run:AI specifically — may run on the A5000 workstation.
- **Not blocked by Tier 8:** unchanged from the original.
- **Tracking:** Tier-7 EPIC. *(Splits into a "runs it" role and a "builds the tooling" role.)*

## Revised Tier 8 — Upstream the correction tool into `sleap-app`

Repurposed from "build the review GUI" (Tier 6.5 now does that) to "make it a first-class part of
the shared app."

- **Deliverable:** migrate/rebuild Tier 6.5's standalone correction tool as native `sleap-app`
  functionality, round-tripping `.slp`.
- **Oracle:** unchanged — a reviewer can load predicted masks in `sleap-app`, accept/reject, and
  re-save valid `.slp`; accepted by SLEAP-team review.
- **Tracking:** unchanged — ties to `talmolab/sleap-app#155`; cross-repo with the SLEAP team;
  buy-in secured in Tier 0.5; draft the sub-issue set and get SLEAP-team go-ahead before filing in
  their repo. **Genuinely off critical path now**, since Tier 6.5 already unblocks real
  review/correction work without it.

## Tier 9 — unchanged

Deliverable, oracle, and tracking stay as currently written.

## Phase 3 addition (parked) — joint pose + segmentation model

**(Possible)** a single model outputting both pose and segmentation masks from a shared backbone
(Mask-R-CNN-style multi-task head). **Not currently possible**: `sleap_nn.config.model_config`'s
`HeadConfig` class is `@oneof`-constrained — "only one attribute of this class can be set, which
defines the model output type" — across all nine head types (`single_instance`, `centroid`,
`centered_instance`, `bottomup`, two multi-class variants, `bottomup_segmentation`,
`centered_instance_segmentation`, `semantic_segmentation`). Verified directly against
`sleap_nn/config/model_config.py` on `main` (2026-07-24). Would require new upstream `sleap-nn`
capability — a combined head type or relaxing the `@oneof` constraint — not achievable from
`sleap-roots-training`'s config layer alone. Parked here, not scheduled, same as the other Phase 3
items.

## Out of scope for this design

- Actually editing `docs/roadmap.md` — this design describes the intended edits; applying them is
  the implementation step (next: `writing-plans`).
- Timing/scheduling decisions (whether Phase 2 starts before "fall", who specifically works on it)
  — explicitly deferred per the scoping question at the start of this brainstorm.
- Filing the Tier-6/6.5/6.7/7/8/9/4.5 EPIC issues themselves — that's JIT, done at each tier's
  actual kickoff per the roadmap's own tracking-issue policy, not as part of this design.
