# Proposal: Compose a training-config wrapper around sleap-nn + `validate` CLI

## Why

The pipeline is config-driven, replacing the old notebook workflow: every experiment should be a
reproducible configuration file, not copy-pasted notebook cells. Roadmap **Tier 1** (issue #16)
needs a typed, validated config foundation so experiments fail fast with clear errors and later
tiers build on a stable contract.

This proposal **supersedes the day-0 draft of this change**. That draft was scaffolded in the
repo's first commit, *before* Tier 0.5 (#9) ran `sleap-nn` even once, and it specified building a
bespoke OmegaConf schema *from scratch* (an invented `dataset / model-backbone / training /
output-W&B` taxonomy) that **never references `sleap-nn`'s own config system**. Tier 0.5 has since
established the reality: `sleap-nn` already ships a complete typed config —
`sleap_nn.config.training_job_config.TrainingJobConfig` (`attrs`-based: `DataConfig` +
`ModelConfig` + `TrainerConfig`, the last already carrying a full `WandBConfig`) — with
module-level validation (`verify_training_cfg`, `check_must_be_set`). Re-declaring those fields
would fork `sleap-nn`'s config layer and violate this repo's own convention that `sleap-nn` /
`sleap-io` are **consumed as libraries, not reimplemented** (`openspec/project.md`). So the design
is inverted: **compose a thin wrapper that adds only what `sleap-nn` lacks, and delegate
training-config validation to `sleap-nn` itself.**

## What Changes

- Add a **thin composition layer** (`sleap_roots_training.config`) over `sleap-nn`'s config. A
  config file is `sleap-nn`'s native `data_config` / `model_config` / `trainer_config` **plus** a
  small repo-owned `experiment` block (species / mode / root_type / dataset identity) — the
  domain metadata `TrainingJobConfig` has no concept of. The wrapper validates its own `experiment`
  fields (`species` / `mode` against `registry/chooser.py`'s `SPECIES_VOCAB` / `MODE_VOCAB`,
  `root_type` against `primary` / `lateral` / `crown`, and rejecting unknown top-level keys rather
  than silently dropping them) and **delegates** the `sleap-nn` portion to `TrainingJobConfig` /
  `verify_training_cfg` rather than re-typing it.
- Add a `sleap-roots-training validate <config.yaml>` CLI subcommand: loads the file, runs the
  wrapper's checks, and reports a clear pass/fail with an appropriate exit code (0 / non-zero).
  Metadata-level checks are **base-install-safe**; the deep `sleap-nn` validation runs when the
  optional `train` extra is importable, else it reports a clear "install `[train]` for full backend
  validation" note (see `design.md` D2).
- Close the **two genuine gaps** `TrainingJobConfig` leaves for a Tier-1 baseline (`design.md` D4):
  (1) `sleap-nn` 0.2.0 has **no default `trainer_config.seed`**, so validation rejects a config
  whose seed is unset — the oracle is built from multiple runs and unseeded spread can't be told
  from signal; (2) the wrapper emits a **fully-resolved** `sleap-nn` config (materializing
  `data_config.preprocessing`), which prevents the post-fit `ConfigAttributeError: Key
  'preprocessing' is not in struct` crash documented in Tier 0.5.
- **Reframe the per-epoch W&B requirement** (`design.md` D3). The prior draft assumed a schema
  field "whose default enables per-epoch logging." There is **no such knob**: `WandBConfig` has no
  cadence field and `TrainerConfig` has no `log_every_n_steps` — per-epoch logging is `sleap-nn` /
  Lightning's *internal* behavior. The requirement becomes **empirical verification** (a small
  `use_wandb=true` run whose `run.scan_history()` returns per-epoch rows), documented in the guide;
  the wrapper only adds the adjacent validation that `use_wandb=true` requires `wandb.entity` +
  `project`.
- Add an **example config**, a **`docs/` training guide** (config → `validate` → `sleap-nn train`
  → read `metrics.*.npz` → confirm per-epoch W&B), a doc-contract test locking the guide, and a
  `docs/CHANGELOG.md` entry.

The PyTorch baseline itself (2–3 same-config runs on held-out root data) is **not** in this change —
it is gated on GPU hardware + a real `.slp` and lands in a follow-up (the guide reserves the section
and reports the legacy TF numbers as a range, per `docs/tf-reference.md`).

## Impact

- **Affected specs:** `training-config` (ADDED — the capability does not yet exist under
  `openspec/specs/`, so all requirements are additive).
- **Affected code:** `src/sleap_roots_training/config.py` (new); `src/sleap_roots_training/cli.py`
  (add `validate` subcommand — imported under an alias, since `cli.py` already binds `config` to
  `registry.config`); `tests/` (new base-install-safe unit + CLI tests, an example-validates test,
  plus one `integration`-marked deep-validation test); `examples/` (new example config); `docs/`
  (new training guide + doc-contract test) and `docs/CHANGELOG.md`; `README.md` (one-line pointer);
  `openspec/project.md` (Architecture Patterns line updated to the composition framing);
  `.github/workflows/ci.yml` (`docs/**` + `examples/**` added to the `paths` filter so the
  doc-contract + example tests actually run).
- **Breaking changes:** none (new package surface; base install stays lean — `sleap_nn` is
  lazy-imported, never at module top).
