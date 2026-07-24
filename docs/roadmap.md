# Generalist SLEAP Root Models — Program Roadmap

**Status:** Approved 2026-06-24 (2 adversarial rounds + focused review) · **Date:** 2026-06-24
**Last revised:** 2026-07-24 (see the dated revision log at the bottom for what changed and why).
**Spec:** the design spec lives in the lab vault + the Notion project (not in this repo).
**Method:** roadmap-driven, tier by tier. Each tier = one just-in-time OpenSpec PR (in this repo)
or, for cross-repo tiers, a coordinated PR set. Oracle-graded. Issues/PRs are filed
**just-in-time** at tier kickoff, not up front.

> **Canonical home:** this file (`docs/roadmap.md`) is the source of truth; it is mirrored to the
> Notion project (the tracker the team watches). Per-tier EPICs and PRs in this repo link back to
> the tiers below.

## Oracle / validation philosophy

**Backend caveat (important):** the old pipeline used the TensorFlow `sleap-train` backend; the
new one uses PyTorch `sleap-nn`. Exact numeric parity is **not** the bar — different backends
converge differently, so demanding "match the old PCK" would falsely fail a healthy model. Instead
we **establish a PyTorch-native baseline** and grade later tiers against *it*, showing the old TF
numbers **for reference only**. Before Tier 0 closes, re-run/extract the old model's documented
results so the TF reference is solid (notebook outputs are fragile).

Tiers are graded against **establish-then-reproduce-or-beat** targets:
- **Keypoint tiers:** establish a PyTorch baseline on a dataset; later tiers match/beat that
  baseline (PCK / localization error). Old TF result shown for context, not as a pass/fail gate.
- **Mask tiers:** meet a mask-AP / mask-IoU target on held-out data (COCO-style, as sleap-nn
  reports).
- **Comparison tiers:** the generalist-vs-specialist table grades against the PyTorch baseline
  (each specialist reproduces its own baseline before the comparison is trusted) and includes
  **trait validation** (e.g. root angle, length, density). Old TF numbers appear as a reference
  column.

Exact tolerances are fixed at each tier's kickoff brainstorm (JIT), grounded in the established
PyTorch baseline.

## Upstream version pins (releases first)

**Default to tagged releases, not commit hashes.**
- **Phase 1 (keypoints):** pin to released `sleap-nn` (v0.2.0+) and its released `sleap-io` —
  keypoint training is in the release, so Phase 1 needs **no commit pins**. (Verify at Tier 0.5.)
- **Phase 2 (masks):** the mask releases are now **cut** — `sleap-nn` **v0.3.0** (adds the mask
  features + a unified `sleap-nn predict` CLI) and `sleap-io` **0.8.0** (latest **0.9.1**) are
  tagged and on PyPI. So Phase 2 pins to those tagged releases; **no commit-hash pin is needed**.
  Phase 1 stays capped below them (`sleap-nn<0.3.0`, `sleap-io<0.8.0`) since that mask line is not
  yet verified here.

Action: at Tier 0.5, confirm Phase-1 release pins work (done — #9). The v0.3.0 / sleap-io 0.8.0
timeline no longer needs coordinating (already released); **confirm Phase-2 pins against those
released tags at Tier 6 kickoff.**

## Work tracks (complementary — everyone works across both)

This roadmap describes **what needs to be done**, not who does it. Work is assigned when its issue
is filed, just-in-time at tier kickoff (see *Tracking-issue policy*). Two tracks describe the kind
of work, not a permanent owner:

- **Engineering track:** pipeline architecture + tooling; the mask-review GUI (Tier 6.5, later
  upstreamed to `sleap-app` in Tier 8).
- **Modeling & evaluation track:** training/sweeps + evaluation, the generalist-vs-specialist
  comparison, labeling strategy/QC, trait validation.
- **Cross-training is a requirement, not a hope:** everyone ships at least one PR in the *other*
  track, and labels a real batch. **Every PR is cross-reviewed by someone from the other track** —
  one reviewer on the engineering angle, one on the modeling/domain angle.
- **Co-owned seams:** the evaluation/comparison harness (Tier 4) and the segmentation
  bootstrap → review/correct loop (Tiers 6 + 6.5).
- Cadence: weekly pairing + async team check-in with Elizabeth. `.slp`/sleap-io is the contract.

---

## Adjacent work — production model registry *(shipped, not tiered)*

Not a roadmap tier, but it lives in this repo and later tiers build on it. Recorded here so the
code is discoverable and **Tier 2 doesn't re-invent a contract that already exists**.

- **What shipped** (#4, #5; archived change
  `openspec/changes/archive/2026-07-05-seed-production-model-registry/`): the `model-registry`
  spec, `src/sleap_roots_training/registry/`, and the `sleap-roots-training seed-registry` CLI. It
  curates the **existing legacy TF models** into the `wandb-registry-sleap-roots-models` registry —
  13 cards carrying the `production` alias (the registry also holds ~87 non-production
  training-run/sweep collections; the 13 are the curated, `ModelCard`-stamped subset), each stamped
  with `ModelCard` metadata (`sleap-roots-contracts`) — so the `WandbRegistrySource` in
  `talmolab/sleap-roots-predict` has something to fetch.
- **This is registry curation, not training.** The weights are legacy and are uploaded as-is. It
  does not advance the keypoint or mask tiers below.
- **Why later tiers care:** seeding fixed the **publishing surface** — the `ModelCard` metadata
  schema, the `production` alias, and the registry path — that this repo's future `sleap-nn`-trained
  models will reuse, whether the weights are legacy or native.
- **Open follow-ups:** #3 (seed the deferred arabidopsis plate models → 15 cards), #7 (accept a
  `wandb login` session, not just `WANDB_API_KEY`; mirrors to `talmolab/sleap-roots-predict`).

## Tier 0 — Scaffold `talmolab/sleap-roots-training` *(prerequisite — not OpenSpec)*

- **Skill:** `scaffolding-lab-python-repo` (day-0 setup, mirrors `sleap-roots-analyze`).
- **Deliverable:** new talmolab repo — uv, ruff/black/pytest, OpenSpec, Claude dev commands, CI;
  `pyproject.toml` pinned to **released** `sleap-nn` / `sleap-io` (commit pin only as a documented
  stopgap if a needed feature is unreleased — see Upstream version pins).
- **Port + archive:** extract reusable concepts (not notebooks) from
  `eberrigan/sleap-roots-training` into documented modules/examples; **archive the old repo** with
  a migration note pointing to the new one.
- **Establish the TF reference:** re-run/extract the old model's documented accuracy on a held-out
  set so there's a solid TensorFlow reference to show alongside the new PyTorch baseline (Tier 1).
- **Shared onboarding:** each person **labels a small batch** *and* **reproduces one training run
  end-to-end** (#1). Reproduction demonstrates the workflow — it is **not** a parity test; see the
  oracle philosophy above.
- **Oracle:** CI green; package installs; `sleap-roots-training --help` runs; OpenSpec
  initialized and an empty change validates; old repo archived; onboarding completed.
- **Tracking:** #1 (onboarding + TF reference), #8 (fixtures + committed TF reference).

## Tier 0.5 — Upstream verification + coordination *(prerequisite checkpoint, week 1)*

- **Verify sleap-nn keypoint training** works end-to-end on a sample dataset (exact `sleap-nn`
  train/predict command documented) — de-risks Tier 1.
- **Lock Phase-1 release pins** (released sleap-nn/sleap-io for keypoints) and **coordinate the
  v0.3.0 / sleap-io 0.8.0 release timeline** with the SLEAP team so Phase 2 can pin to releases.
- **Secure SLEAP-team buy-in for talmolab/sleap-app#155** Phase-1 scope (render + accept/reject): draft
  the scope as a comment/sub-issue and get **written sign-off including an expected PR-review
  turnaround**. If no go-ahead, Tier 8 drops to a contingency / Phase 3 — **it is not on the
  mask-training critical path** (see Tier 7). Assign a `sleap-app` ramp task at Tier 0.5 kickoff —
  reading its issues/code and optionally landing a small non-blocking PR during Phase 1 — so
  Tier 8 (Phase 2) isn't a cold start whenever it's picked up.
- **Confirm repo name** `talmolab/sleap-roots-training`.
- **Oracle:** documented keypoint train/predict run; pins locked; talmolab/sleap-app#155 scope acknowledged by the
  SLEAP team (or Tier 8 reclassified).
- **Tracking:** #9.

## Phase 1 — Keypoints + pipeline (summer)

### Tier 1 — Core single-dataset training on sleap-nn, config-driven
- **Deliverable:** OmegaConf-configured train+eval of one model on one dataset via the sleap-nn
  backend; experiment is a config file, not a notebook; **training guide / README** included.
- **Per-epoch metrics MUST be logged to W&B.** The legacy TF runs logged *only* final eval
  summaries — `scan_history()` returns zero rows, so there is no loss curve and no epoch count.
  That gap made the Tier-0 onboarding repro (#1) impossible to compare against the original run.
  Log per-epoch train/val loss and the stopping epoch.
- **Oracle:** establish a **PyTorch-native baseline** (2–3 **same-config** runs to get a stable
  range — not a hyperparameter sweep, which is a different axis of variation) on the held-out data;
  document config, hyperparameters, loss curves, and accuracy. This baseline — not exact parity with
  the old TF model — is the reference for later tiers; the old TF number is reported alongside **as
  a range, not a point** (#8), because same-config seed/replicate spread is real (~1.5–1.73×
  `dist_avg` in the legacy runs; see `docs/tf-reference.md`) and must not be mistaken for
  architecture-driven variation from a sweep. *(W&B versioning is retrofitted in Tier 2.)*
- **Tracking:** Tier-1 EPIC; foundation change `openspec/changes/add-config-schema/`.
  **Depends on** Tier 0.5 (#9).

### Tier 2 — Dataset registry + W&B artifact integration
- **Deliverable:** labeled `.slp` datasets and trained models versioned as W&B artifacts
  (`sleap-roots-labels`, `sleap-roots-models`) with run→artifact lineage.
- **Builds on the shipped publishing surface** (see *Adjacent work* above): reuse the existing
  `ModelCard` contract, `production` alias, and `sleap-roots-models` registry path — do **not**
  define new ones. The models registry already carries 13 `production`-aliased collections (the
  registry has ~100 collections total; most are non-production sweep/run artifacts).
- **Labels need a contract of their own.** The `sleap-roots-labels` registry currently stores
  provenance as boolean-key metadata and `data_path`s pointing at deleted temp directories, so a
  label set cannot be traced to its experiment — and `cyl` (labels) vs `cylinder` (models) means a
  model cannot be joined to the labels it trained on. A `LabelCard` mirroring `ModelCard`, plus a
  row-level sample manifest (the ad hoc labeling-package build process already computes this
  provenance in a personal script, not yet ported into a shared repo — see #10), is a prerequisite
  for the lineage oracle.
- **Oracle:** round-trip a dataset and a model through the registries; lineage reproduces a run;
  **a dry-run sweep (≈5 configs, 1 species) launches and logs with full lineage** — verifying the
  registry is solid **before** the expensive Tier 3 sweeps.
- **Tracking:** Tier-2 EPIC; #10 (LabelCard contract), #11 (backfill existing collections).
  *(Good home for a cross-track engineering PR.)*

### Tier 2.5 — Labeling strategy + seed QC *(before sweeps)*
- **Deliverable:** documented labeling strategy/coverage plan + a **minimal seed set of QC
  checks** (e.g. in-frame, no isolated keypoints, confidence bounds) run over the curated data.
- **Oracle:** seed QC flags a planted set of known label errors; curation for Tier 3 is QC-passed.
- **Tracking:** Tier-2.5 EPIC. *(Pairs a domain lens with a checks/tooling lens. Full QC tooling
  is Tier 5; this prevents dirty data from reaching the expensive sweeps.)*

### Tier 2.7 — Skeleton unification + node-count selection *(before generalist training)*
- **Characterize first:** measure the **inter-node spacing distribution** on a sample of labeled
  roots per species/root-type. Labeling is node-*position* based, so spacing may not be true arc
  length. If spacing is ~uniform, arc-length resampling is fine; if not, use **parameterization-
  aware / spline resampling** (e.g. Catmull-Rom / B-spline through the labeled nodes) so curved
  roots aren't distorted. Anchor at base + tip.
- **Harmonize** each combined dataset's roots to a **single common skeleton per root type** via the
  chosen resampling.
- **Node count is a tuned choice, validated by performance — with a node-count-*normalized*
  metric.** Raw PCK is **not** comparable across node counts (its denominator changes); use **mean
  per-node localization error (px) + trait fidelity** (root length/angle/curvature) as the sweep
  metric. Produce the accuracy-vs-node-count curve and pick **at/past the plateau**. Be cautious
  about **upsampling above source node counts** (it fabricates training targets) — prefer counts
  the labels actually support, justified by the sweep.
- **Scope nuance:** unify *within a comparable root type across species* (e.g. all primary-root
  datasets) — **not** across biologically different root types (primary / lateral / seminal /
  crown keep their own skeletons).
- **Oracle (apples-to-apples, on the unified skeleton):**
  1. **Geometric + trait fidelity** — resampled roots reproduce the original traced path within a
     pixel tolerance **and** preserve root length/angle/curvature within tolerance (catches
     systematic curvature loss that a path tolerance alone can miss); node count uniform across the
     combined dataset.
  2. **Performance fidelity** — a model trained + evaluated **on the unified skeleton** meets/beats
     the per-dataset baseline *re-measured on that same unified skeleton* (not native-vs-unified),
     using the normalized metric, and holds up under **per-source-dataset cross-validation** (no
     single source's traits degrade) — so the model isn't silently compensating for distortion.
- **Tooling:** check `sleap-io` for existing skeleton/instance resampling; if absent, build a local
  utility and consider upstreaming it.
- **Depends on queryable label metadata** (#10): node counts and node names are today recoverable
  only from free-text artifact descriptions, so "measure spacing per species/root-type" cannot be
  scripted until `LabelCard` lands.
- **Tracking:** Tier-2.7 EPIC. *(Pairs selection + eval with resampling + sweep tooling.
  Tier 3 generalist training depends on this.)*

### Tier 3 — Multi-dataset / generalist training + sweeps
- **Deliverable:** train a generalist model across ≥2 species **on the unified skeleton (Tier
  2.7)**; config-driven sweeps **on Run:AI when available, or the A5000 workstation otherwise —
  compute location isn't prescribed, given Run:AI's sparse availability.** **Draft the comparison
  matrix** (crops × root types) with Elizabeth to scope Tier 4.
- **Oracle:** generalist model matches/exceeds the old generalist-notebook result on held-out
  test sets; comparison matrix drafted. *(Depends on Tier 2 lineage + Tier 2.7 unified skeleton.)*
- **Tracking:** Tier-3 EPIC. *(Splits into a "runs it" role and a "builds the tooling" role.)*

### Tier 4 — Evaluation + generalist-vs-specialist comparison harness
- **Deliverable:** train per-crop/root-type specialists; comparison harness emitting a
  generalist-vs-specialist table with localization metrics **and trait validation** (root angle,
  length, density, etc.).
- **Oracle:** each specialist reproduces its known single-dataset accuracy within tolerance
  (tolerance set at kickoff from Tier-1/3 results) before the comparison is trusted; table
  complete across the drafted matrix; trait validation included. For an apples-to-apples
  comparison, **specialists are retrained on the unified skeleton (Tier 2.7)** so generalist and
  specialists are trained *and* evaluated under identical skeleton conditions (do **not** merely
  resample a native specialist's predictions — that biases against it).
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
- **Deliverable:** the full QC tooling/CLI over labels, extending the Tier-2.5 seed checks.
- **Oracle:** QC flags the **same planted error set** from Tier 2.5 (now measured to a
  precision/recall target set at kickoff).
- **Tracking:** Tier-5 EPIC. *(Good home for a cross-track modeling/eval PR.)*

## Phase 2 — Segmentation masks (fall)

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

### Tier 9 — Mask generalist-vs-specialist comparison
- **Deliverable:** comparison table for mask models (generalist vs per-crop specialist).
- **Oracle:** specialists reproduce known mask metrics before the comparison is trusted; table
  includes mask-AP/IoU **and trait validation**.
- **Tracking:** Tier-9 EPIC.

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

---

## Execution cadence & safeguards

From the pragmatism review — keep throughput high and de-risk the likely-overrun tiers:

- **Weekly team check-in** (Elizabeth + the team, ~30 min): blockers, next-tier kickoff plan,
  compute/infra status (Run:AI, W&B), SLEAP-app coordination. **Escalation rule:** if a tier's
  oracle isn't trending toward met by mid-tier, escalate immediately — don't silently debug.
- **Right-size the per-tier review:** keep the adversarial OpenSpec *proposal* review, but run it
  **light for the straightforward tiers (1–3)** and **full-depth for the complex/cross-repo tiers
  (4 and 8)**. Cross-track review is a ~30-min async "other-angle" check, not a gate.
- **Smoke-test early, not late:** run the Tier-2 dry-run sweep in the *first* days of the tier so
  W&B-lineage bugs surface with time to fix.
- **Cap the comparison matrix:** start Tier 3/4 at ~2 crops × ≤2 root types (≈4–8 models); expand
  only after the harness is proven. Lock the matrix at Tier-3 kickoff; don't grow it mid-sweep.
- **Pair-program the Tier-4 harness:** it's the complexity peak and a paper output — define the
  comparison schema + trait metrics in writing first, add unit tests on mock data, pair rather
  than async-review.
- **Tier 2.5 / 3 kickoffs are timeboxed planning meetings** (define seed errors + tolerance; lock
  the matrix) — written, not improvised mid-tier.

## Tracking-issue policy (JIT, hybrid)
- **This roadmap does not assign people to tiers.** Issues are filed just-in-time at tier kickoff
  and **assigned then**, against who is actually available and what they should be learning.
- One EPIC issue per tier (roadmap row links it), filed at tier kickoff.
- Per-change sub-issues filed when a tier is decomposed into changes — then, not upfront.
- Every PR links its EPIC + the roadmap tier/change it advances; closes its sub-issue on merge.
- **Cross-PR / cross-review requirement** (see Work tracks) is tracked here too.
- Cross-repo (`sleap-app`): draft the set, get the SLEAP-team go-ahead, then file.
- Feature work uses the repo's Claude workflow: run `/new-feature`, which itself orchestrates
  `/openspec:proposal` → `/review-openspec` → (pauses for your explicit approval) →
  `/openspec:apply` (TDD) → `/pre-merge-check`. Issues should name it so contributors don't
  improvise a process.

## Open roadmap decisions
- The comparison matrix (which crops × root types) — drafted at Tier 3, locked at Tier 4.
- The common skeleton / node count per root type for unification — set at Tier 2.7.
- Phase boundary timing (summer→fall), contingent on available team hours.

## Roadmap review reconciliations (2026-06-24)

Adversarial 4-lens review (factual / sequencing / completeness / scope). Factual + scope lenses
clean. Reconciled findings:
- **BLOCKING (sequencing):** sleap-nn mask code on `main`, not tagged → added the **Upstream
  version pins** section + commit-hash pins in Tier 0 + Tier 0.5 verification.
- **BLOCKING (sequencing):** Tier 8 cross-repo buy-in/coupling → buy-in moved to **Tier 0.5
  (week 1)**; **Tier 7 explicitly decoupled** from Tier 8 (programmatic mask correction interim).
- **BLOCKING (completeness):** old repo archive missing → added **port + archive** to Tier 0.
- **IMPORTANT (sequencing):** QC too late → added **Tier 2.5** (labeling strategy + seed QC)
  before sweeps; Tier 5 is now full tooling.
- **IMPORTANT (sequencing):** W&B lineage before sweeps → Tier 2 oracle now requires a dry-run
  sweep; Tier 3 depends on it.
- **IMPORTANT (sequencing):** sleap-nn keypoint-training unverified → Tier 0.5 check.
- **IMPORTANT (completeness):** cross-training not guaranteed → **cross-PR + cross-review made a
  requirement** in Intern tracks + tracking policy; onboarding added to Tier 0 oracle.
- **IMPORTANT (completeness):** trait validation implicit → made explicit in Tier 4 + Tier 9
  oracles + the oracle philosophy.
- **IMPORTANT (completeness):** comparison-matrix scope → drafted at Tier 3.

**Round 2 (2026-06-24)** — factual / sequencing / completeness lenses clean (all round-1 fixes
confirmed RESOLVED, 100% spec coverage, no new cycles). Pragmatism lens added:
- **BLOCKING (oracle realism):** old backend is TensorFlow `sleap-train`, new is PyTorch
  `sleap-nn` → exact parity is the wrong bar. Reframed the **oracle philosophy + Tier 1** to
  establish a PyTorch baseline and show TF numbers for reference; added a Tier-0 step to extract a
  solid TF reference.
- **IMPORTANT (coordination):** strengthened Tier 0.5 #155 buy-in to **written scope + review
  turnaround + fallback**, and added an Anirudh **sleap-app ramp during Phase 1**.
- **IMPORTANT (execution):** added the **Execution cadence & safeguards** section (weekly
  check-in + escalation, right-sized reviews, early W&B smoke test, matrix cap, Tier-4
  pair-programming, timeboxed kickoffs).
- **MINOR:** unified the Tier 2.5 / Tier 5 QC "planted error set" wording.

**Focused review — Tier 2.7 (2026-06-24)** — added the skeleton-unification tier (user request),
then reviewed it. Reconciled:
- **BLOCKING (metric confound):** raw PCK isn't comparable across node counts → sweep now uses a
  **node-count-normalized metric** (per-node localization error + trait fidelity).
- **BLOCKING (resampling validity):** arc-length assumes even spacing but labeling is
  position-based → added a **characterize-spacing-first** step + spline/parameterization-aware
  resampling for curved roots.
- **BLOCKING (comparison fairness):** performance oracle now compares **on the same unified
  skeleton** (not native-vs-unified); **Tier 4 specialists are retrained on the unified skeleton**
  rather than having predictions resampled.
- **IMPORTANT:** oracle gained **trait fidelity + per-source cross-validation** (so a model can't
  hide distortion); **Tier 6** SAM prompts use unified-skeleton keypoints; check `sleap-io` for
  existing resampling utilities before building.

**Roadmap revision (2026-07-13)** — assignment stripped; onboarding findings folded in.
- **IMPORTANT (structure):** **Names removed from tiers.** Every `**Lead:** <person>` line is gone
  and the "Intern tracks" section is now **Work tracks**. The roadmap says *what* needs doing;
  issues are filed JIT and **assigned at filing time**. Fixed-in-advance ownership never survived
  contact with reality — it bound the same work (the config schema) to two different people at
  once.
- **IMPORTANT (clarity):** **Tier 0 onboarding clarified.** Reproducing a training run demonstrates
  the *workflow*; it is **not** a parity test. This was already implied by the oracle philosophy but
  not stated where the onboarding step lives, and the ambiguity cost real time (#1).
- **IMPORTANT (reproducibility):** **Tier 1 gained a hard requirement:** per-epoch metrics **must**
  be logged to W&B. The legacy TF runs logged only final summaries (`scan_history()` → zero rows),
  which made a repro impossible to compare against its original.
- **IMPORTANT (oracle accuracy):** **Tier 1 oracle now reports the TF reference as a range**, not a
  point — same-config seed/replicate spread is ~1.5–1.7× in `dist_avg` (#8). *Correction: an earlier
  draft of this entry and of #8 mischaracterized a `max_stride` receptive-field **sweep** (four
  different configs) as "replicates of the same config" and quoted a ~2× spread across the whole
  sweep; re-verified against the actual per-run configs and fixed here and in #8.*
- **IMPORTANT (completeness):** **Adjacent work section added.** The shipped production model
  registry (seed-registry CLI, `model-registry` spec) was absent from the "source of truth"
  roadmap, so its code had no home and #3/#7 had no tier. Tier 2 silently depended on the
  `ModelCard` publishing surface it established; that dependency is now written down.
- **MINOR:** **Issue links added:** Tier 0 → #1, #8. Tier 0.5 → #9. Tier 1 → `add-config-schema`.
  Tier 2 → #10, #11. Adjacent work → #3, #7.
- **IMPORTANT (lineage):** **Tier 2 gained a label-contract prerequisite, and Tier 2.7 a dependency
  on it** (#10). The `sleap-roots-labels` registry stores provenance as boolean keys and dead
  `data_path`s, and its `cyl`/`cylinder` split means models cannot be joined to their training
  labels.
- **MINOR:** **Tracking policy** now names the `/new-feature` Claude workflow so contributors don't
  improvise.
- **MINOR (self-review, post-#12 review pass):** fixed a self-contradiction ("trio" vs "team"
  cadence wording), a temporally-incoherent "whoever leads Tier 8" phrase (Tier 8 is Phase 2, but
  the ramp task it described was needed during Phase 1, before this revision's own JIT-assignment
  policy would assign anyone to it), an imprecise "13 legacy collections" count (the registry holds
  ~100 collections; 13 carry `production`), and a `/build-labeling-package` slash-command reference
  that doesn't resolve outside a personal script. Also restored one historical-log line this
  revision had inadvertently altered (`#155` → `talmolab/sleap-app#155`) back to its original
  wording, since editing prior dated entries — even for a good reason — contradicts "history is
  append-only"; all live/forward references elsewhere in the doc remain correctly qualified.

**Roadmap revision (2026-07-21)** — upstream mask releases are out; Phase-1 pins locked (Tier 0.5 / #9).
- **IMPORTANT (upstream pins):** **The Phase-2 mask releases are cut.** `sleap-nn` **v0.3.0**
  (masks + a unified `sleap-nn predict` CLI) and `sleap-io` **0.8.0**/**0.9.1** are now tagged on
  PyPI, so the "Upstream version pins" body (Phase-2 bullet + Action) has been corrected: Phase 2
  pins to released tags and **no v0.3.0 / sleap-io 0.8.0 cut needs coordinating**. Source: the
  Tier 0.5 verification spike (#9), which locked the Phase-1 pins (`sleap-nn>=0.2.0,<0.3.0`,
  `sleap-io>=0.7.1,<0.8.0`, `torch>=2.5.0`) as an optional `train` extra and confirmed keypoint
  train/predict on the `sleap-nn` backend. `openspec/project.md` "Important Constraints" was
  corrected to match.
- **MINOR:** Tier 0.5 is **not** marked "done" here — completion is tracked by #9 + the CHANGELOG
  per the JIT tracking policy; this entry only corrects now-false forward-looking facts.

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
