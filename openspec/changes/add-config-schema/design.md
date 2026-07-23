## Context

Roadmap **Tier 1** (issue #16) is the first config-driven train/eval tier, gated on Tier 0.5 (#9,
done). It needs a typed, validated config foundation so an experiment is a reproducible file, and it
must establish a PyTorch-native baseline (a follow-up PR) that later tiers reproduce-or-beat.

This change **supersedes its own day-0 draft**. That draft — the repo's first OpenSpec change,
written before Tier 0.5 ran `sleap-nn` once — specified a bespoke OmegaConf schema built *from
scratch* (`dataset / model-backbone / training / output-W&B`) and never referenced `sleap-nn`'s own
config. Tier 0.5 then established the real surface, so the draft is both stale and redundant.

Exploration (of `talmolab/sleap-nn` at `v0.2.0`, the version pinned in `uv.lock`; the extra is not
installed locally) established the true starting point:

- `sleap_nn.config.training_job_config.TrainingJobConfig` (`attrs`) composes `DataConfig` +
  `ModelConfig` + `TrainerConfig`; `TrainerConfig` already carries `use_wandb`, `seed`, and a full
  `WandBConfig`. Validation is module-level: `verify_training_cfg(cfg)` merges the config onto
  `OmegaConf.structured(TrainingJobConfig())`, resolves (`throw_on_missing`), and runs
  `check_must_be_set` — whose **only** hard requirement is "≥1 backbone AND ≥1 head." There is **no
  `from_yaml`**; `load_sleap_config*` are legacy TF-`training_config.json` importers, not YAML
  loaders.
- `TrainingJobConfig` has **no domain metadata** (species / mode / age / root_type) — that is this
  repo's own `registry/cards.py::Card` concept.
- `WandBConfig` has **no logging-cadence field** and `TrainerConfig` has **no `log_every_n_steps`**,
  so "per-epoch logging" is not expressible as a config value.
- `sleap-nn` 0.2.0 has **no default `seed`** and crashes *after* the fit loop on a config lacking
  `data_config.preprocessing` (`ConfigAttributeError`), per the Tier 0.5 runbook.
- `sleap_nn` lives only in the optional `[train]` extra; CI installs `--group dev` only and runs
  `-m "not integration"`. `omegaconf>=2.3.0` and `click>=8.0.0` are already **base** deps.

## Goals / Non-Goals

- **Goals:** a thin composition layer over `sleap-nn`'s config (a repo-owned `experiment` block +
  delegated `sleap-nn` validation); a `validate` CLI with a clean exit-code contract that works on a
  base install and deep-validates when `[train]` is present; the two genuine reproducibility/safety
  gaps closed (explicit seed; resolved-config emission); an example config; a `docs/` training guide
  + doc-contract test; a CHANGELOG entry.
- **Non-Goals:** re-declaring any `sleap-nn` config field; a schema field that "enables" per-epoch
  W&B logging (there is none — verified empirically instead); the PyTorch baseline runs themselves
  (follow-up PR, gated on GPU + a real `.slp`); W&B dataset/model artifact versioning + the label
  registry / `LabelCard` (Tier 2); training/predict orchestration beyond `validate` (the guide drives
  `sleap-nn train` directly, as in Tier 0.5).

## Decisions

### D1 — Compose around `TrainingJobConfig`; do not reimplement it

The wrapper adds **only** an `experiment` metadata block and delegates the `data_config` /
`model_config` / `trainer_config` portion to `sleap-nn`'s `TrainingJobConfig` /
`verify_training_cfg`. Rationale: `sleap-nn` already ships the typed schema + validation the day-0
draft proposed to hand-build; forking it would duplicate a large, evolving surface and violates the
repo convention that `sleap-nn` / `sleap-io` are **consumed as libraries, not reimplemented**
(`openspec/project.md`). Alternatives: (a) the bespoke from-scratch schema — **rejected**: stale,
redundant, guaranteed to drift from `sleap-nn`; (b) a passthrough that adds nothing and just shells
to `sleap-nn train` — **rejected**: it captures no domain identity for the baseline and closes none
of the 0.2.0 gaps (D4).

### D2 — Lazy-import `sleap_nn`; split base-safe vs. train-gated validation

`config.py` MUST NOT `import sleap_nn` at module top, or it would break the base install / CI, which
never installs `[train]` (repo precedent: the lazy `import wandb` inside `cli.py`). So validation is
two-tier: **base-install-safe** checks (experiment metadata against `SPECIES_VOCAB` / `MODE_VOCAB`;
seed presence; W&B-enablement pairing) run everywhere using only OmegaConf; the **deep** check
(`verify_training_cfg` → backbone/head + full resolve) and resolved-config emission lazily
`import sleap_nn` and run only when the extra is importable, otherwise emitting a clear non-failing
"install `[train]`" note. Consequence: the deep-path test is `@pytest.mark.integration` +
`pytest.importorskip("sleap_nn")` (deselected in CI); the metadata/seed/wandb tests are ordinary CI
tests. Alternative: make `validate` hard-require `[train]` — **rejected**: it strands base-install
users and leaves nothing for the CI matrix to exercise on the `validate` path.

Two enforcement details from the pre-approval review: (a) the skip-note branch is the path CI
*actually* runs (CI never installs `[train]`), yet its contract — base-safe checks still run, a clear
note prints, exit 0 — is easy to leave untested, and a box that *does* have `[train]` would silently
take the deep path in that test instead. So the lazy import is routed through a **monkeypatchable
seam** (`config._deep_validation_available()` / `_import_sleap_nn()`) a base-safe test patches to
force the absent branch deterministically. (b) The "no top-level `sleap_nn`" invariant gets an
explicit lock (`assert "sleap_nn" not in sys.modules` after a base-safe `validate_config`), on top of
the implicit guard that `tests/test_smoke.py` already imports `cli.py` (→ `config.py`) on a
`sleap_nn`-less CI host.

### D3 — Per-epoch W&B logging is verified empirically, not "enabled" by a field

The day-0 spec required "a W&B logging configuration whose default enables per-epoch logging."
`sleap-nn` exposes no such knob (no `WandBConfig` cadence field, no `TrainerConfig`
`log_every_n_steps`), so a schema field claiming to enable it would be fiction. Per-epoch logging is
Lightning's default *inside* `sleap-nn`. **Decision:** satisfy the roadmap's "per-epoch metrics MUST
be logged" by **verifying it empirically** — a short `use_wandb=true` run whose `run.scan_history()`
returns per-epoch rows — and documenting that check + result in the guide. The wrapper's only W&B
contribution is the adjacent validation that `use_wandb=true` requires `wandb.entity` + `project`
(a real config error class, unlike the phantom cadence field). This is the issue's explicit
instruction ("verify empirically … rather than assuming a new config validation layer"). If the
empirical check ever shows per-epoch is *not* default, that is an upstream `sleap-nn`/Lightning
concern (documented limitation), not something a passthrough field can fix.

### D4 — Close the two genuine 0.2.0 gaps: explicit seed + resolved-config emission

These are the only places the wrapper adds validation beyond delegating, because they are real gaps
`TrainingJobConfig` leaves open on 0.2.0:

1. **Seed required.** `trainer_config.seed` defaults to `None` on 0.2.0 (the `seed: 42` default
   arrives in 0.3.0). The Tier-1 oracle is built from multiple same-config runs; unseeded spread is
   indistinguishable from signal, and every later tier grades against that baseline. So
   `validate_config` rejects an unset seed — a repo policy stricter than `sleap-nn`'s default, which
   is the point.
2. **Resolved-config emission.** `run_training` reads `config.data_config.preprocessing.*` off the
   user config *after* the fit loop and crashes if it is absent. Because the schema carries a
   `preprocessing` factory default, merging the user config onto
   `OmegaConf.structured(TrainingJobConfig())` **materializes** it. So `to_sleap_nn_config` emits
   that fully-resolved config, and the guide trains from it — turning a latent crash into a
   structural guarantee. This is the one guarantee whose only test is `[train]`-gated, so its
   verification is an explicit **manual `pytest -m integration tests/test_config.py`** run on the
   `[train]` box, recorded in the PR body (the spec scenario asserts the *structural* completeness the
   test actually checks — that the emitted config carries a populated `preprocessing` block — not a
   full training run).

### D5 — Keep the change-id and capability name; the `experiment` block is the sole new schema

Keep the change-id `add-config-schema` and capability `training-config`: `docs/roadmap.md` and
`docs/tf-reference.md` reference the change **by name**, and it is the sole active change on the
refreshed `main`, so renaming buys nothing and breaks references. The revision stays additive
(`## ADDED Requirements` only) since `training-config` is not yet applied under `openspec/specs/`.
The `experiment` block is the wrapper's **only** newly-declared schema; everything else is
`sleap-nn`'s, by reference.

## Risks / Trade-offs

- **Version-coupling to `sleap-nn` 0.2.0 internals.** Delegating to `verify_training_cfg` /
  `check_must_be_set` couples us to a module-level API. Mitigation: the base-safe checks (metadata,
  seed, wandb-pairing) do not depend on it; the deep path is integration-tested where `[train]` is
  installed, so a breaking upstream rename surfaces there, not silently. The `<0.3.0` cap (Tier 0.5
  D2) bounds the drift.
- **`validate` gives *partial* assurance on a base install.** Without `[train]`, backbone/head and
  full type resolution are unchecked. Mitigation: the CLI says so explicitly (non-failing note); the
  guide's real train step runs under `[train]`, where deep validation is active.
- **Empirical per-epoch W&B evidence is observable, not CI-testable.** Mitigation: it is an explicit
  manual task whose evidence lives in the guide + PR body; it is never faked as a passing CI test
  (Tier 0.5 precedent). A standing job that trains + hits W&B would need torch + network and cannot
  run on the CI matrix.
- **Seed-required is stricter than `sleap-nn`.** A user copying a bare `sleap-nn` config will be
  rejected until they add a seed. That friction is intended (reproducible baselines) and the error
  message explains it; the example config ships a seed.
- **`experiment`-vs-`sleap-nn` key split could confuse.** Mitigation: one documented top-level
  `experiment` key; everything else is verbatim `sleap-nn` config, so a user who knows `sleap-nn`
  needs to learn only the one addition. Unknown top-level keys are rejected (not silently dropped), so
  a typo like `trainer_confg` fails loudly rather than vanishing a whole block.
- **Doc-lock vs. the reserved-baseline placeholder.** The doc-contract test forbids `TODO`/`TBD`
  anywhere, but the guide must reserve a to-be-filled baseline section. Mitigation: reserve it with an
  explicit marker containing neither token, and have the test **positively assert that marker string
  is present** — so the reservation is locked in (can't be silently dropped) while a bare `TODO` still
  fails. The follow-up baseline PR replaces the marker with the numbers.
- **The doc-lock/example tests only bite if CI runs them.** `docs/**` and `examples/**` are outside
  the current CI `paths` filter, so a docs-only PR (including the follow-up baseline) would skip the
  matrix and merge the lock un-run. Mitigation: this change adds `docs/**` + `examples/**` to the
  filter (task 5.5), making the lock real and un-poison-pilling the follow-up.

## Migration Plan

Additive; no existing behavior changes. The **committed** unit is green per slice — the red→green
TDD loop is *local*; test + implementation land in the same commit (Tier 0.5 precedent; never push a
red commit). The concrete 8-commit sequence is the **Commit Plan** at the bottom of `tasks.md`
(proposal revision → `config.py`+schema → `validate` CLI → seed → resolved-emission/deep-gate → W&B
pairing → docs/example/CI-paths → empirical backfill). CI stays green throughout (base install; the
deep-path test self-deselects; within the PR every push — including docs-only commits — runs the full
matrix against HEAD). The change is archived in a **separate** chore PR (`cleanup-merged`), per the
#4 → #5 precedent — this PR does not move it under `openspec/changes/archive/`. Rollback: the surface
is new and additive; `git revert` of the feature commits restores the prior lean CLI (revert the
`config.py` commits as a range, since 4–6 append to `validate_config` in one file).

## Open Questions

- **Baseline dataset (follow-up).** The 2–3 same-config baseline runs need the real
  Arabidopsis-primary-root cylinder `.pkg.slp` behind the legacy TF group
  `20250625_cyl_arabidopsis_primary_receptive_field` — to be sourced from Elizabeth (`eberrigan`),
  including the train/val split. Not blocking this change; the guide reserves the section.
- **Where the empirical W&B check runs.** The per-epoch verification can run on the fly sample on
  CPU/MPS (no GPU / no root data). Whether to log it online or `WANDB_MODE=offline` + sync is left to
  execution; the guide records whichever was used and the `scan_history()` result.
- **Deferred from Tier 0.5: pin strength.** The GPU-box install bypasses `uv.lock`, so a `sleap-nn`
  0.2.x patch could shift behavior with no auto re-verify before results feed W&B lineage. This
  change does not record training *results* (the baseline PR does), so the decision (exact-pin vs.
  a re-verify gate) is still owed before that follow-up.
