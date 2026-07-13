# Generalist SLEAP Root Models — Program Roadmap

**Status:** Approved 2026-06-24 (2 adversarial rounds + focused review) · **Date:** 2026-06-24
**Spec:** the design spec lives in the lab vault + the Notion project (not in this repo).
**Method:** roadmap-driven, tier by tier. Each tier = one just-in-time OpenSpec PR (in this repo)
or, for cross-repo tiers, a coordinated PR set. Oracle-graded. Issues/PRs are filed
**just-in-time** at tier kickoff, not up front.

> **Canonical home:** this file (`docs/roadmap.md`) is the source of truth; it is mirrored to the
> Notion project (the tracker the interns watch). Per-tier EPICs and PRs in this repo link back to
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
- **Phase 2 (masks):** the mask features are on `main` but not yet tagged — latest `sleap-nn`
  release is v0.2.0 (masks pending **v0.3.0**), and the mask data layer is `sleap-io` **0.8.0**,
  unreleased (latest tag v0.7.1; `sleap-nn`'s own `main` currently commit-pins `sleap-io` for this
  reason). **These are our lab's repos**, so the clean path is to get **v0.3.0 / sleap-io 0.8.0
  cut** before Phase 2 (fall) and pin to those releases. A commit-hash pin is only a **stopgap** if
  a mask tier arrives before the release lands.

Action: at Tier 0.5, confirm Phase-1 release pins work and **coordinate the v0.3.0 / sleap-io 0.8.0
release timeline with the SLEAP team**. Re-verify at Tier 6 kickoff.

## Work tracks (complementary — everyone works across both)

This roadmap describes **what needs to be done**, not who does it. Work is assigned when its issue
is filed, just-in-time at tier kickoff (see *Tracking-issue policy*). Two tracks describe the kind
of work, not a permanent owner:

- **Engineering track:** pipeline architecture + tooling; the mask-review GUI (Tier 8).
- **Modeling & evaluation track:** training/sweeps + evaluation, the generalist-vs-specialist
  comparison, labeling strategy/QC, trait validation.
- **Cross-training is a requirement, not a hope:** everyone ships at least one PR in the *other*
  track, and labels a real batch. **Every PR is cross-reviewed by someone from the other track** —
  one reviewer on the engineering angle, one on the modeling/domain angle.
- **Co-owned seams:** the evaluation/comparison harness (Tier 4) and the SAM-predict →
  review/correct loop (Tiers 6 + 8).
- Cadence: weekly pairing + async trio check-in with Elizabeth. `.slp`/sleap-io is the contract.

---

## Adjacent work — production model registry *(shipped, not tiered)*

Not a roadmap tier, but it lives in this repo and later tiers build on it. Recorded here so the
code is discoverable and **Tier 2 doesn't re-invent a contract that already exists**.

**What shipped** (#4, #5; archived change `openspec/changes/archive/2026-07-05-seed-production-model-registry/`):
the `model-registry` spec, `src/sleap_roots_training/registry/`, and the
`sleap-roots-training seed-registry` CLI. It curates the **existing legacy TF models** into the
`wandb-registry-sleap-roots-models` registry — 13 selection cards, each stamped with `ModelCard`
metadata (`sleap-roots-contracts`) and the `production` alias — so the `WandbRegistrySource` in
`talmolab/sleap-roots-predict` has something to fetch.

**This is registry curation, not training.** The weights are legacy and are uploaded as-is. It does
not advance the keypoint or mask tiers below.

**Why later tiers care:** seeding fixed the **publishing surface** — the `ModelCard` metadata
schema, the `production` alias, and the registry path — that this repo's future `sleap-nn`-trained
models will reuse, whether the weights are legacy or native.

**Open follow-ups:** #3 (seed the deferred arabidopsis plate models → 15 cards), #7 (accept a
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
  mask-training critical path** (see Tier 7). During Phase 1, whoever leads Tier 8 **ramps on
  `sleap-app`** (reads issues/code, optionally lands a small non-blocking PR) so Phase 2 isn't a
  cold start.
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
- **Oracle:** establish a **PyTorch-native baseline** (2–3 runs to get a stable range) on the
  held-out data; document config, hyperparameters, loss curves, and accuracy. This baseline — not
  exact parity with the old TF model — is the reference for later tiers; the old TF number is
  reported alongside **as a range** (#8), because replicate spread is real. *(W&B versioning is
  retrofitted in Tier 2.)*
- **Tracking:** Tier-1 EPIC; foundation change `openspec/changes/add-config-schema/`.
  **Depends on** Tier 0.5 (#9).

### Tier 2 — Dataset registry + W&B artifact integration
- **Deliverable:** labeled `.slp` datasets and trained models versioned as W&B artifacts
  (`sleap-roots-labels`, `sleap-roots-models`) with run→artifact lineage.
- **Builds on the shipped publishing surface** (see *Adjacent work* above): reuse the existing
  `ModelCard` contract, `production` alias, and `sleap-roots-models` registry path — do **not**
  define new ones. The models registry is already non-empty (13 legacy collections).
- **Labels need a contract of their own.** The `sleap-roots-labels` registry currently stores
  provenance as boolean-key metadata and `data_path`s pointing at deleted temp directories, so a
  label set cannot be traced to its experiment — and `cyl` (labels) vs `cylinder` (models) means a
  model cannot be joined to the labels it trained on. A `LabelCard` mirroring `ModelCard`, plus the
  `sample_manifest.csv` from `/build-labeling-package`, is a prerequisite for the lineage oracle.
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
  2.7)**; config-driven sweeps on Run:AI. **Draft the comparison matrix** (crops × root types)
  with Elizabeth to scope Tier 4.
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

### Tier 5 — Full labeling-QC tooling
- **Deliverable:** the full QC tooling/CLI over labels, extending the Tier-2.5 seed checks.
- **Oracle:** QC flags the **same planted error set** from Tier 2.5 (now measured to a
  precision/recall target set at kickoff).
- **Tracking:** Tier-5 EPIC. *(Good home for a cross-track modeling/eval PR.)*

## Phase 2 — Segmentation masks (fall)

### Tier 6 — SAM-predict glue (poses → predicted masks)
- **Deliverable:** a pipeline step wrapping sleap-nn `run_sam_segmentation` to turn keypoint
  poses into `PredictedSegmentationMask` for review.
- **Oracle:** predicted masks on a sample (using keypoints from the unified skeleton, Tier 2.7)
  reach a mask-IoU threshold vs a hand-checked set.
- **Tracking:** Tier-6 EPIC. *(Re-verify sleap-nn mask state + pins at kickoff.)*

### Tier 7 — Pipeline mask training
- **Deliverable:** train `bottomup_segmentation` / `centered_instance_segmentation` via the
  pipeline; config-driven.
- **Oracle:** mask model meets a mask-AP/IoU target on held-out data.
- **Tracking:** Tier-7 EPIC. *(Splits into a "runs it" role and a "builds the tooling" role.)*
- **Not blocked by Tier 8:** mask corrections for training can be done programmatically
  (`sleap-io` `PredictedSegmentationMask.to_user()`) or via the desktop path in the interim. The
  web GUI (Tier 8) is a quality-of-life accelerator, **not** a critical-path dependency.

### Tier 8 — Mask review/correct GUI in `sleap-app` (talmolab/sleap-app#155 Phase-1) *(cross-repo, off critical path)*
- **Deliverable:** render + accept/reject predicted masks in the web app, round-tripping `.slp`.
- **Oracle:** a reviewer can load predicted masks, accept/reject, and re-save valid `.slp`;
  accepted by SLEAP-team review.
- **Tracking:** ties to existing talmolab/sleap-app#155; cross-repo with the SLEAP team; buy-in secured
  in Tier 0.5; **draft the sub-issue set and get SLEAP-team go-ahead before filing in their repo.**

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
- Feature work uses the repo's Claude workflow: `/new-feature` → `/openspec:proposal` →
  `/review-openspec` → approval → `/openspec:apply` (TDD) → `/pre-merge-check`. Issues should name
  it so contributors don't improvise a process.

## Open roadmap decisions
- The comparison matrix (which crops × root types) — drafted at Tier 3, locked at Tier 4.
- The common skeleton / node count per root type for unification — set at Tier 2.7.
- Phase boundary timing (summer→fall), contingent on available intern hours.

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
- **IMPORTANT (coordination):** strengthened Tier 0.5 talmolab/sleap-app#155 buy-in to **written scope + review
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

**Roadmap revision (2026-07-09)** — assignment stripped; onboarding findings folded in.
- **Names removed from tiers.** Every `**Lead:** <person>` line is gone and the "Intern tracks"
  section is now **Work tracks**. The roadmap says *what* needs doing; issues are filed JIT and
  **assigned at filing time**. Fixed-in-advance ownership never survived contact with reality — it
  bound the same work (the config schema) to two different people at once.
- **Tier 0 onboarding clarified.** Reproducing a training run demonstrates the *workflow*; it is
  **not** a parity test. This was already implied by the oracle philosophy but not stated where the
  onboarding step lives, and the ambiguity cost real time (#1).
- **Tier 1 gained a hard requirement:** per-epoch metrics **must** be logged to W&B. The legacy TF
  runs logged only final summaries (`scan_history()` → zero rows), which made a repro impossible to
  compare against its original.
- **Tier 1 oracle now reports the TF reference as a range**, not a point — replicates of the same
  config span ~2x in `dist_avg` (#8).
- **Adjacent work section added.** The shipped production model registry (seed-registry CLI,
  `model-registry` spec) was absent from the "source of truth" roadmap, so its code had no home and
  #3/#7 had no tier. Tier 2 silently depended on the `ModelCard` publishing surface it established;
  that dependency is now written down.
- **Issue links added:** Tier 0 → #1, #8. Tier 0.5 → #9. Tier 1 → `add-config-schema`.
  Tier 2 → #10, #11. Adjacent work → #3, #7.
- **Tier 2 gained a label-contract prerequisite, and Tier 2.7 a dependency on it** (#10). The
  `sleap-roots-labels` registry stores provenance as boolean keys and dead `data_path`s, and its
  `cyl`/`cylinder` split means models cannot be joined to their training labels.
- **Tracking policy** now names the `/new-feature` Claude workflow so contributors don't improvise.
