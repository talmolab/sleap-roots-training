# Generalist SLEAP Root Models — Program Roadmap

**Status:** Approved 2026-06-24 (2 adversarial rounds + focused review) · **Date:** 2026-06-24
**Last revised:** 2026-08-07 (see the dated revision log at the bottom for what changed and why).
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

**Not to be confused with `sleap-roots-pipeline`'s separate roadmap** (`docs/bloom-integration/roadmap.md`
there, tracking A0–A4 service-integration milestones across repos). That roadmap's now-closed
**A3-predict parity gate** (`sleap-roots-pipeline#15`) validated the *inference engine* — sleap-nn
reproduces classic-SLEAP's predictions on the *same already-trained* legacy weights. Tier 2.2 below
is the *training*-pipeline counterpart: a different question (can sleap-nn reproduce a model's
legacy accuracy *from scratch*), tracked here, not there.

Tiers are graded against **establish-then-reproduce-or-beat** targets:
- **Keypoint tiers:** establish a PyTorch baseline on a dataset; later tiers match/beat that
  baseline (PCK / localization error). Old TF result shown for context, not as a pass/fail gate.
- **Mask tiers:** meet a mask-AP / mask-IoU target on held-out data (COCO-style, as sleap-nn
  reports).
- **Comparison tiers:** the generalist-vs-specialist table grades against the PyTorch baseline
  (each specialist reproduces its own baseline before the comparison is trusted) and includes
  **trait validation** (e.g. root angle, length, density). Old TF numbers appear as a reference
  column.
- **Production-fleet tier (Tier 2.2 — the one deliberate exception):** for a model that is
  *already shipped* and about to be replaced by a sleap-nn-trained retraining, the old TF number
  **is** the bar (within tolerance) — regressing a model already in production is a different risk
  than a keypoint tier's general accuracy target, where no prior deployed number exists to protect.
  Every other tier above keeps TF as context, not a gate.

Exact tolerances are fixed at each tier's kickoff brainstorm (JIT), grounded in the established
PyTorch baseline (or, for Tier 2.2, the production model's own legacy TF number).

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
- **Co-owned seams:** the evaluation/comparison harness (Tier 4), the segmentation
  bootstrap → review/correct loop (Tiers 6 + 6.5), and the fleet-wide training-parity gate
  (Tier 2.2 — registry/dedup tooling is engineering, per-model training + metric comparison is
  modeling/eval).
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
  turnaround**. Tier 8 is off the mask-training critical path regardless of this outcome (see
  Tier 7) — Tier 6.5 already provides the review/correction path; this buy-in is only needed for
  Tier 8's later upstream-migration goal. Assign a `sleap-app` ramp task at Tier 0.5 kickoff —
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
- **Oracle — ESTABLISHED (2026-07-29, #21):** a **PyTorch-native baseline** (2–3 **same-config**
  seeds for a stable range — not a hyperparameter sweep) on the v000 held-out val split (Arabidopsis
  primary-root, multi-plant cylinder, bottom-up, `output_stride 4`): `dist_avg` **30.1–37.8 px**,
  `dist_p50` **17.7–21.2 px**, `vis_recall` **0.85–0.91** (all instances detected; per-epoch W&B
  logging confirmed; config, hyperparameters, loss curves documented). This baseline — not TF
  parity — validates the config-driven pipeline and methodology (matching architecture/sigma alone
  isn't sufficient without the training schedule too, or a faithful config falsely appears to
  collapse; `sleap-nn#718`); it does **not** itself carry the production fleet's reference weight —
  v000 isn't a production model, and that role now belongs to Tier 2.2's per-model gate. The old TF
  numbers are reported **as a range, not a point** and for context only (in **pixels**: stride 16
  `dist_avg` 23.7–39.0 @ `vis_recall` 0.50–0.56; stride 32 29.9–30.2 @ 0.78–0.81; stride 64 21.7–21.9
  @ 0.87; stride 8 collapsed to 0 predictions; see `docs/tf-reference.md`). **Correction
  (2026-08-06):** an earlier version of this entry quoted the TF numbers as 0.99–2.08 px. Those
  values are **millimeters** from a lab post-processing step, not SLEAP's pixel metrics, and the
  "PyTorch is 20–40× worse" reading they produced was wrong. In matching units the PyTorch
  baseline's `dist_avg` sits inside the TF range, and it detects 44/44 instances on every seed where
  no TF run exceeds 43/44. On `vis_recall` two of its three seeds (0.912, 0.885) clear TF's best of
  0.872 and seed 43 (0.850) does not. Caveat carried forward: the error is dominated by
  detection/association quality, **not** a resolution ceiling (higher output resolution buys no
  gain). A `sigma` ablation settled the earlier `output_stride 2` collapse: it was too-tight confmap
  targets at `sigma 2.5` (`sigma 5.0` trains stably on all 3 seeds), not the loss or resolution.
  Full write-up: `docs/training.md` ("PyTorch baseline"). *(W&B versioning is retrofitted in
  Tier 2.)*
- **Tracking:** Tier-1 EPIC; foundation change `openspec/changes/add-config-schema/`; baseline
  established in #21. **Depends on** Tier 0.5 (#9).

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
  provenance in a personal script, not yet ported into a shared repo — see #26), is a prerequisite
  for the lineage oracle.
- **Shared/generalist models have no way to be represented once.** `ModelCard.species` is a single
  required string, so a model trained once but serving multiple species (confirmed: one
  primary-root model already serves arabidopsis/canola/pennycress) is registered N times —
  currently 13 registrations for only 8 physically distinct weight sets, each a full separate
  ~75MB artifact upload (training#39, surfaced while building A3-predict's parity harness — see
  Tier 2.2). Decide during this tier: retype `ModelCard.species` to a tuple, adopt a
  canonical-registration + lightweight-alias scheme, or accept the duplication as a documented
  tradeoff — #39 lays out the concrete options. Tier 2.2 dedups on `weights_checksum` in the
  interim regardless of which way this goes.
- **Oracle:** round-trip a dataset and a model through the registries; lineage reproduces a run;
  **a dry-run sweep (≈5 configs, 1 species) launches and logs with full lineage** — verifying the
  registry is solid **before** the expensive Tier 3 sweeps.
- **`LabelCard` stays single-species.** Unlike `ModelCard` (#39 — one physical model shared across
  species, no way to express that), a `LabelCard` never represents more than one species. A
  generalist model's multi-species training data is combined from separate single-species
  `LabelCard`-backed `.slp` files **at training time**, not via a pre-built or pre-registered
  combined artifact — `sleap-nn`'s `DataConfig.train_labels_path`/`val_labels_path` already accept
  a list of paths and split each independently. This requires the combined files to share a
  skeleton (Tier 2.7) and does not reproduce any original combined split exactly, which is an
  accepted tradeoff in favor of clean per-species versioning/lineage and future per-dataset
  data-engineering work (per-dataset splits, per-dataset contribution to a generalist model).
- **Tracking:** Tier-2 EPIC; #10 (LabelCard contract — shipped, `sleap-roots-contracts#24`), #11
  (backfill existing collections onto `LabelCard`, now unblocked — carries an explicit requirement
  to verify each collection is actually single-species before backfilling, not just trust its
  name), #39 (registry-duplication decision, models only). *(Good home for a cross-track
  engineering PR.)*

### Tier 2.2 — Per-model training-backend parity (sleap-nn vs. legacy TF, full production fleet)
- **Deliverable:** for every **physically distinct** production model (dedup on `weights_checksum`,
  not the 13 `ModelCard` registrations — see Tier 2's registry-duplication decision / #39), retrain
  via the sleap-nn backend. **Use that model's exact legacy TF config and dataset — not a
  modernized config, not a "TF-inspired" one, the literal same split and hyperparameters TF used**,
  following the schedule-*and*-architecture-matched translation approach Tier 1 validated the hard
  way (#21, #36): matching resolution + sigma alone was not sufficient — the training
  schedule/step-count had to match too, or a faithful config falsely appears to collapse. If a
  production model's exact original dataset cannot be **confidently identified** (real risk — see
  #11's own finding that 6 of the 8 existing label collections have gaps in *provenance metadata*,
  not necessarily lost frames — the images themselves are recoverable from the W&B artifact, but
  broken `data_path`s and undocumented fields make it hard to confirm a given collection is the
  exact one a legacy model trained on), flag and exclude that model from this tier's gate rather
  than approximating it; a fabricated "close enough" split must never quietly stand in for the real
  one. **A model excluded this way is held, not exempted** — it does not proceed into Tier 3 until
  its dataset is actually recovered/confirmed, so the fleet-wide "gate cleared" claim is never
  diluted by an unresolved gap. Compare the
  resulting model's evaluation metrics directly against that model's own real legacy TF numbers,
  per model, not pooled — the same discipline `docs/tf-reference.md` already applies to the one
  Tier 1 dataset, extended to the full fleet.
- **Verify the legacy reference's units before trusting it.** PR #33 found its own cited TF
  `dist_avg` numbers were **millimeters from a lab post-processing CSV, not pixels from SLEAP's own
  `metrics.val.npz`** — a unit mismatch that made the PyTorch baseline look ~20–40× worse than it
  actually is; corrected, it's competitive (inside TF's own pixel range, ahead on recall). Read each
  production model's legacy reference from its own `metrics.val.npz` directly, not from a downstream
  analysis artifact, before this tier's numbers go into anyone's gate.
- **Relationship to A3-predict (explicit, so the two aren't conflated):** `sleap-roots-pipeline#15`
  / `sleap-roots-predict#33` proved sleap-nn's **inference engine** reproduces classic-SLEAP's
  predictions on the *same already-trained* legacy weights. This tier proves sleap-nn's **training**
  pipeline can reproduce each model's legacy accuracy *from scratch* — a different failure mode: a
  training backend that can't reproduce known-good accuracy is a training bug; a healthy-looking
  training run whose weights don't work at inference time (already ruled out, fleet-wide) is a
  separate one.
- **Oracle (hard gate):** a production model does not proceed into Tier 3 until its sleap-nn
  from-scratch reproduction meets/beats its legacy TF number within tolerance, or a documented,
  investigated exception is recorded — mirror `pipeline#15`'s rice-crown-age6-10 investigation (rule
  out a real difficulty confound before assuming a backend defect). Exact tolerance is fixed **at
  this tier's kickoff** (JIT, per the convention above), grounded in two already-real datapoints, not
  decided from a blank slate:
  - the real legacy TF numbers per production model (extends `docs/tf-reference.md`'s per-model
    discipline to the full fleet)
  - the per-model inference-parity relative-delta numbers `sleap-roots-predict`'s harness already
    measured (`pipeline#15` / `predict#33`'s 8-row table) — so this tier's *training*-side tolerance
    is not confounded with a gap the inference-parity gate already explained and closed

  These two datapoints aren't confounded because they measure different failure surfaces:
  inference-parity asks whether the *same already-trained* weights produce the same predictions
  under a different runtime (numerical/engine precision — `sleap-roots-pipeline#15` /
  `sleap-roots-predict#33`'s question). Training-parity asks whether training *from scratch*
  reproduces known-good accuracy at all (recipe/schedule fidelity — PR #21/#36's finding that a
  faithful architecture can still "collapse" purely from a training-schedule mismatch, unrelated to
  inference-engine precision). A gap in one doesn't predict or bound a gap in the other, so the
  inference-delta table informs how much slack to expect from engine-level noise without
  substituting for the training-side tolerance itself.
- **Depends on:** Tier 2 (registry/lineage — need it to enumerate "every production model" against
  tracked, versioned data) and #39 (train once per distinct `weights_checksum`, not once per card,
  or this retrains the same physical model up to 4×). **Sequenced, not parallel:** kickoff waits
  for #11 (backfill) and #39 (dedup decision) to close — retraining "the actual pipeline" against
  the real dataset registry is the point of this tier, so it can't start against registry loose
  ends.
- **Tracking:** Tier-2.2 EPIC (filed at kickoff, JIT); links #21 / #36 (the Tier-1 methodology this
  generalizes), #39 (dedup blocker), `sleap-roots-pipeline#15` + `sleap-roots-predict#33` (the
  inference-side precedent + reusable ground-truth/tolerance-decision methodology).

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
- **Depends on queryable label metadata** (#11): node counts and node names for the existing 8
  label collections are today recoverable only from free-text artifact descriptions; `LabelCard`
  itself has landed (#10), but "measure spacing per species/root-type" cannot be scripted until
  those collections are backfilled onto it (#11).
- **Tracking:** Tier-2.7 EPIC. *(Pairs selection + eval with resampling + sweep tooling.
  Tier 3 generalist training depends on this.)*

### Tier 3 — Multi-dataset / generalist training + sweeps
- **Deliverable:** train a generalist model across ≥2 species **on the unified skeleton (Tier
  2.7)**; config-driven sweeps **on Run:AI when available, or the A5000 workstation otherwise —
  compute location isn't prescribed, given Run:AI's sparse availability.** **Draft the comparison
  matrix** (crops × root types) with Elizabeth to scope Tier 4.
- **Oracle:** generalist model matches/exceeds the old generalist-notebook result on held-out
  test sets; comparison matrix drafted. *(Depends on Tier 2 lineage, Tier 2.7 unified skeleton, and
  Tier 2.2's per-model hard gate — a production model held by Tier 2.2 does not feed into this
  tier's sweeps.)*
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
  surface. Note: shipping N per-species specialists instead of one generalist has an ongoing
  retraining/re-validation cost this tier doesn't size — flag that cost explicitly in the
  documented decision wherever N is greater than 1, so it's an informed tradeoff, not a free one.
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
  - **Talmo's (the SLEAP/`sleap-nn` maintainer) pose-derived pseudo-mask heuristic** (fixed-width
    band around the skeleton — cheap, no training required, reported to get decent results; exact
    documentation location not yet tracked down — confirm with Talmo directly at Tier 6 kickoff
    before relying on it)
  - **Real hand-labeled masks**, where #23's inventory already has them (cylinder Arabidopsis;
    smaller rice/sorghum/soybean batches)

  Pick (and document) whichever produces usable, review-ready masks for that crop's actual
  morphology — mirrors this roadmap's existing "establish then reproduce-or-beat" oracle
  philosophy rather than assuming one method wins everywhere.
- **Oracle:** a per-crop comparison table (method vs. mask-IoU/clDice (centerline Dice — a
  topology-aware metric better suited to thin, tubular root shapes than plain IoU) against a small hand-checked
  reference set) with a documented decision per crop. If no method clears a usable bar for a given
  crop, that crop is flagged and descoped from Phase 2 until Tier 6.5's correction GUI can produce
  labels for it from scratch — don't force a low-quality method through just to have an answer.
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
- **Prototype risk:** `sam3-segmenter` and `labelroi` are early-stage prototypes, not versioned
  packages — unlike this repo's disciplined `sleap-nn`/`sleap-io` release pinning (see "Upstream
  version pins"), there's no pin or stability guarantee here. Confirm their current state and
  scope the actual build-out effort at Tier 6.5 kickoff before committing to a timeline; this is a
  cross-language (JS + `sleap-io.js`, against an otherwise Python-scaffolded repo) deliverable and
  likely belongs in the "full-depth review" bucket alongside Tiers 4 and 8 (see Execution cadence),
  not the "light review" bucket.

### Tier 6.7 — Segmentation labeling strategy + coverage plan
- **Deliverable:** per-crop assessment of whether #23's existing label inventory is sufficient for
  Tier 7 training, or whether more labels are needed — plus a minimal QC checklist for
  segmentation masks (mask-specific analog of Tier 2.5's pose checklist: no holes/disconnected
  fragments, tight boundaries, sane foreground/background balance). Where more labels are needed,
  Tier 6.5's correction GUI is the tool used to produce them.
- **Oracle:** seed QC flags a planted set of known mask errors (mirrors Tier 2.5's oracle); a
  documented per-crop verdict ("enough data" / "needs N more labeled frames") before Tier 7 sweeps
  begin.
- **Depends on:** Tier 6 (need the per-crop method comparison first to assess label sufficiency).
  Only the remediation path (producing more labels where the inventory falls short) depends on
  Tier 6.5's correction GUI — the sufficiency assessment itself can start as soon as Tier 6 lands,
  in parallel with Tier 6.5 being built, mirroring how Tier 2.5 (pose) runs before Tier 5's full
  QC tooling rather than waiting on it.
- **Tracking:** Tier-6.7 EPIC.

### Tier 7 — Pipeline mask training
- **Deliverable:** train `bottomup_segmentation`/`centered_instance_segmentation` (or whole-frame
  semantic, chosen by crop morphology per the guidance below) via the config-driven pipeline from
  Tier 1, starting
  from Talmo's validated recipe as the default rather than an open hyperparameter search:
  whole-frame UNet, output-stride 4, BCE/Dice 0.5/0.5, no `pos_weight`; tiling only when a crop's
  objects are smaller than the tile (compact/lateral roots — never elongated primaries); top-down
  instance segmentation for compact-root crops (bottom-up is not yet deployable as-is per the
  campaign's audit — mislabels/misses roughly half even after the grouping-field retrain).
- **Sweep clause (parity with Tier 3's pose sweeps):** for crops where Talmo's campaign already
  validated the recipe on that exact crop (e.g. cylinder Arabidopsis — SAM3 zero-shot clDice
  0.808 vs. trained UNet clDice 0.866, n=17 held-out images), reuse it directly. For crops it didn't cover, or
  where the audit flagged single-seed scope and found every instance/backbone result is
  soy_lateral-only (not "most" — reported p-values there are per-frame variance, not per-seed), run a
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
  achievable from this repo's config layer alone. No current owner or ask-path for raising this
  with the `sleap-nn`/SLEAP team (unlike Tier 0.5's `sleap-app#155` buy-in template) — if this
  becomes worth pursuing, it needs the same treatment: draft the ask, get written scope + turnaround
  from the SLEAP team, before any implementation work starts here.

---

## Execution cadence & safeguards

From the pragmatism review — keep throughput high and de-risk the likely-overrun tiers:

- **Weekly team check-in** (Elizabeth + the team, ~30 min): blockers, next-tier kickoff plan,
  compute/infra status (Run:AI, the A5000 workstation, W&B), SLEAP-app coordination. **Watch for
  A5000 contention:** Tiers 2.2, 3, 6, and 7 can all fall back to the same single workstation when
  Run:AI is unavailable — if more than one needs it concurrently, that's a real bottleneck to
  surface at the weekly check-in, not something this roadmap schedules around in advance. Tier 2.2
  alone implies roughly **16–24 training runs** (8 physically distinct production models × Tier
  1's own 2–3-same-config-seed precedent), so it's a real contender for that contention, not just a
  documentation nicety.
  **Escalation rule:** if a tier's
  oracle isn't trending toward met by mid-tier, escalate immediately — don't silently debug.
- **Right-size the per-tier review:** keep the adversarial OpenSpec *proposal* review, but run it
  **light for the straightforward tiers (1, 2, 2.5, 2.7, 3)** and **full-depth for the
  complex/cross-repo tiers (2.2, 4, and 8)**. Tier 2.2 is a hard gate on Tier 3 whose tolerance
  leans on methodology from two other repos (`sleap-roots-pipeline`, `sleap-roots-predict`) — the
  same cross-repo-dependency reasoning that puts Tier 8 in this bucket. Cross-track review is a
  ~30-min async "other-angle" check, not a gate.
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
- Whether/how to resolve the shared-model-registry duplication (#39) — decided during Tier 2;
  Tier 2.2 dedups on `weights_checksum` in the interim either way.
- Tier 2.2's exact per-model tolerance — fixed at Tier 2.2 kickoff, grounded in the real legacy TF
  numbers and `sleap-roots-predict`'s measured inference-parity deltas (see Tier 2.2).

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

**Roadmap revision (2026-08-04)** — production-model training-backend parity, prompted by the
now-closed A3-predict inference-parity gate.
- **IMPORTANT (completeness):** **Tier 2.2 added** (per-model training-backend parity: sleap-nn vs.
  legacy TF, full production fleet) — generalizes Tier 1's single-dataset baseline methodology
  (#21, hard-won through PR #33's schedule-vs-loss investigation, #36) to every production model, as
  a **hard gate** before Tier 3's generalist sweeps build on the sleap-nn training pipeline broadly.
  Complements, not duplicates, the now-closed A3-predict inference-engine parity gate
  (`sleap-roots-pipeline#15`, closed; `sleap-roots-predict#33`) — that gate validated the inference
  engine on fixed legacy weights; this tier validates the training pipeline's ability to reproduce
  legacy accuracy from scratch, per model.
- **IMPORTANT (registry correctness):** **Tier 2 gained an open decision**: #39 found the
  production registry holds 13 `ModelCard` registrations for only 8 physically distinct models,
  because `ModelCard.species` can't express a shared/generalist model. Flagged for resolution during
  Tier 2; Tier 2.2 dedups on `weights_checksum` in the interim.
- **MINOR:** noted the distinction between this roadmap and `sleap-roots-pipeline`'s separate
  Bloom-integration roadmap (`docs/bloom-integration/roadmap.md`), so the closed A3-predict
  (inference) gate isn't mistaken for covering this new (training) gate.
- Related, closed without a roadmap change needed: `sleap-roots-predict#32` (contracts `0.1.0a6`
  pin bump confirmed safe against the live registry; no code change required).

**Roadmap revision (2026-08-06)** — follow-up clarity pass on Tier 2.2, a hard-won lesson from
PR #33's own units bug, and coordination decisions from a progress review (sequencing + label
registry species scope).
- **IMPORTANT (clarity):** **Tier 1's oracle reworded** — it validates the config-driven pipeline
  and methodology, not the production fleet's reference; that role now belongs to Tier 2.2. The
  prior wording ("...is the reference for later tiers") predated Tier 2.2 and overclaimed Tier 1's
  ongoing role.
- **IMPORTANT (rigor):** **Tier 2.2 gained two additions**, both prompted by PR #33 continuing to
  surface real problems after the 2026-08-04 entry above:
  1. The "exact legacy TF config and dataset" requirement is now its own emphasized sentence
     (previously a clause inside a longer sentence about dedup) plus an explicit gap policy: a
     production model whose exact original dataset can't be recovered is flagged and excluded from
     the gate, never approximated — mirroring `#11`'s own "do not invent values" rule.
  2. **A units-verification requirement**, direct from PR #33 (`668bb83`, 2026-08-06): its own cited
     TF `dist_avg` numbers turned out to be millimeters from a lab post-processing CSV, not pixels
     from SLEAP's own `metrics.val.npz` — inflating the apparent PyTorch-vs-TF gap ~20–40× before
     correction (corrected, the baseline is competitive). Tier 2.2 must read each production
     model's legacy reference from its own `metrics.val.npz` directly, not a downstream analysis
     artifact.
- **MINOR:** PR #33 also independently reproduced the A3-predict inference-parity finding from a
  different angle — scoring a legacy run's saved predictions with `sleap_nn`'s Evaluator matches
  SLEAP's own stored metrics to every printed digit — and found TF itself has a `max_stride 8`
  collapse (0 predicted instances), the same failure mode as the `output_stride 2` sleap-nn
  collapse this tier's methodology addresses. Noted for context; no roadmap structure change from
  this item alone.
- **IMPORTANT (sequencing):** **Tier 2.2's "Depends on" line now says explicitly that kickoff is
  sequenced after #11/#39, not run in parallel with them** — Tier 2.2 is meant to retrain against
  the real dataset registry, so it can't start while Tier 2's own registry loose ends are still
  open.
- **IMPORTANT (Tier 2 completeness):** **`LabelCard` will not mirror `ModelCard`'s species-tuple
  question (#39).** Every `LabelCard` stays single-species; multi-species generalist training data
  is combined from separate single-species files at training time (`sleap-nn`'s `DataConfig`
  already accepts a list of `.slp` paths and splits each independently). Posted as a decision on
  #11, which also now carries an explicit requirement to verify each of the 8 existing collections
  is actually single-species (a preliminary spot-check found no evidence of mixing, but wasn't
  exhaustive) before backfilling it onto `LabelCard`.
- **MINOR:** **#16** (Tier-1 EPIC) and **#10** (label-registry tracking issue) closed — both
  tracked work that had already shipped (#21/PR #33, and `sleap-roots-contracts#24` respectively).

**Roadmap revision (2026-08-07)** — merge-conflict reconciliation, prompted by an adversarial PR
review of the branch carrying the above 2026-08-04/2026-08-06 entries.
- **IMPORTANT (accuracy):** **Tier 1's Oracle bullet reconciled with `main`.** This branch's
  reworded bullet (validates methodology, doesn't carry the production-fleet reference weight) was
  drafted before `main` picked up PR #33's landed baseline (`ESTABLISHED`, real numbers, the
  units-correction paragraph). A naive merge-conflict resolution would have silently dropped PR
  #33's established results from the roadmap; reconciled by keeping PR #33's content and layering
  this branch's role-reframing sentence on top.
- **MINOR (citation accuracy):** the schedule-matching finding's bare `#718` reference is now
  qualified as `sleap-nn#718` (an upstream issue, not one in this repo) — every other cross-repo
  reference in this document is qualified this way and this one wasn't.
- **MINOR (staleness):** two references to the now-closed #10 were updated to point at the issues
  that actually still track that work: Tier 2's "not yet ported into a shared repo" note now cites
  #26 (not #10, which only tracked the `LabelCard` contract itself); Tier 2.7's label-metadata
  dependency now cites #11 (the backfill — `LabelCard` itself already landed via #10).
- **IMPORTANT (survivorship bias):** **Tier 2.2's exclusion policy now says explicitly that an
  excluded model is held, not exempted** — it does not proceed into Tier 3 until its dataset is
  actually recovered/confirmed. Without this, "excluded from the gate" was ambiguous between a
  safe hold and a silent exemption that would let the fleet-wide "gate cleared" claim overstate
  readiness on exactly the hardest-to-verify models. Also tightened the #11 citation backing this
  policy: the real risk is unrecoverable *provenance metadata* on 6 of 8 label collections, not
  lost frames (which remain pullable from the W&B artifact) — the previous wording overstated it as
  full dataset loss.
- **IMPORTANT (rigor):** **Tier 2.2's tolerance grounding gained the actual decomposition
  argument**, not just an assertion: inference-parity deltas (`pipeline#15`/`predict#33`) and
  training-parity tolerance measure different failure surfaces — engine-numerical precision on
  already-trained weights vs. training-recipe/schedule fidelity from scratch (PR #21/#36) — so a
  gap in one doesn't predict a gap in the other.
- **MINOR (resourcing):** **Tier 2.2 added to the "Watch for A5000 contention" bullet**, with its
  implied ~16–24 training runs (8 models × Tier 1's 2–3-seed precedent) named explicitly — it was
  previously omitted despite sitting immediately before Tiers 3/6/7 on the same watchlist.
- **MINOR (completeness):** **Tier 3's "Depends on" line now names Tier 2.2's hard gate**, not just
  Tier 2/2.7 — a model Tier 2.2 holds does not feed into Tier 3's sweeps.
