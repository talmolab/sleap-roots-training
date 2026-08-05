# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- The wandb credential guard (`seed-registry --execute` / `--verify`) now accepts a resolvable
  wandb credential — `WANDB_API_KEY` **or** a netrc entry for `api.wandb.ai` written by
  `wandb login` — instead of requiring `WANDB_API_KEY`. The netrc file is located the way wandb
  locates it (`NETRC` env var, else `~/.netrc`, else `~/_netrc`), so a login session is honored on
  every platform (including Windows `~/_netrc`). Fail-fast with a clear error is retained when no
  credential is resolvable anywhere; a malformed netrc — or a netrc entry with a blank/absent
  password — is treated as "no credential" (mirroring wandb's own resolver), so a stale login fails
  before the confirmation prompt rather than deep inside `wandb.init()`.

### Added
- `sleap-roots-training labeling`: the labeling-package generator, ported from a personal vault
  repo into `sleap_roots_training.labeling` (#26). Four commands — `select`, `copy-images`,
  `build`, `validate` — replace four `uv run` scripts driven against hardcoded paths on one
  machine. A **labeling package** is now a named contract: a directory carrying the `.slp` per root
  type, the curated `images/`, `sample_manifest.csv` with one row per labeled frame,
  `package_metadata.yaml`, and a generated `README.md`, with no dependency on the machine that
  produced it. `labeling validate` checks all of it and is the entry point `publish-labels` (#10)
  calls before upload. See `docs/labeling-packages.md`.

  **For anyone who ran the vault scripts**, the behavior changes that affect you: the built `.slp`
  **embeds its images**, so a package no longer breaks when its source paths go away (six of the
  eight published collections carry `repaired_from: "v0"` because that happened); a given seed now
  **selects different plants**, because the draw is a stable hash ordering rather than
  `pandas.sample` — which is what makes widening a selection produce a superset instead of a
  different label set; three views are `[1, 19, 37]` rather than `[1, 25, 49]`; skeletons come from
  a committed per-crop table and an uncovered crop **fails** instead of getting soybean's node
  counts; and every silent failure is now a failure — an unresolvable source image, a duplicate
  curated filename, a scan whose view count contradicts `--total-views`, a scan with no
  predictions, and an empty selection each stop the run rather than warning and reporting success.
  Adding frames to a published package is re-derive and republish, not edit in place; the reason is
  in the guide.
- `sleap-roots-training validate <config.yaml>` and `sleap-roots-training emit <config.yaml>`: a
  config-driven training-config schema + CLI. A config is `sleap-nn`'s native
  `data_config`/`model_config`/`trainer_config` **plus** a repo-owned `experiment` block
  (species/mode/root_type/dataset). `validate` checks the experiment metadata, requires an explicit
  integer `trainer_config.seed` (0.2.0 has no default) and a `data_config.preprocessing` block
  (0.2.0 crashes post-fit without it), checks the W&B-enablement pairing, and **delegates** deep
  validation to `sleap-nn`'s `verify_training_cfg` when the `train` extra is installed (else a
  clear skip note) — it does not reimplement `sleap-nn`'s config. `emit` writes the sleap-nn-native
  config with the `experiment` block stripped (sleap-nn rejects that key) for `sleap-nn train`.
  `sleap_nn` is lazy-imported and `emit` is base-safe, so the base install/CI stay lean.
- `docs/training.md` config-driven training guide + `examples/arabidopsis_primary_cylinder.yaml`,
  locked by `tests/test_training_docs.py` and `tests/test_examples_validate.py`.
- Shared test-fixture layer (`tests/conftest.py`) with `tiny_matrix`, `stub_models_root`,
  `isolate_wandb_env` (clears the wandb/registry env vars **and** `NETRC` and repoints
  `HOME`/`USERPROFILE`), and TF-reference payload loaders.
- Committed TensorFlow reference baseline: the `config`/`summary` of the seven canonical
  `20250625_cyl_arabidopsis_primary_receptive_field` runs under `tests/fixtures/tf_reference/`
  (captured by `scripts/pull_tf_reference.py`), documented in `docs/tf-reference.md` and locked by
  `tests/test_tf_reference.py`. The group is a `max_stride` sweep, not a replicate set; `oks_map` is
  excluded as broken and the observability gap (no per-epoch logging) is recorded for Tier 1.
- `sleap-roots-training seed-registry`: seed the production wandb model registry from the
  committed selection matrix. Publishes the current legacy root models as `type="model"`
  artifacts with flat `ModelCard` selection metadata and the `production` alias — the
  surface the `sleap-roots-predict` warm worker reads. Defaults to a dry run; `--execute`
  (with `--yes`/`--force`/`--only`) publishes; `--verify` re-runs the consumer read path.
- `sleap_roots_training.registry` package: env-driven config, the provenance-stamped
  `model_selection.yaml` (7 rows → 13 cards over 8 SHA256-pinned models), card expansion,
  legacy-model resolution (SHA256-verified unzip), run-config lineage, and the
  publish/link/verify helpers.
- Runtime deps `wandb` and `sleap-roots-contracts`.
- Optional `train` extra: the Phase-1 `sleap-nn` keypoint backend
  (`sleap-nn>=0.2.0,<0.3.0`, `sleap-io>=0.7.1,<0.8.0`, `torch>=2.5.0`), kept out of the base
  install so the cross-platform CI matrix stays lean. Install with
  `sleap-roots-training[train]`.
- `docs/training-backend.md`: verified `sleap-nn` keypoint train/predict runbook (install,
  GPU check, train + predict commands, and the GPU compute-capability / arch findings).
- `tests/test_train_extra.py` (CI-safe pins contract) and `tests/test_gpu.py`
  (integration-marked GPU smoke test, skipped without a CUDA device).

## [0.0.1a0] - 2026-06-24

### Added
- Initial repository scaffold: package skeleton, CLI entry point
  (`sleap-roots-training --help`), test suite, CI, and OpenSpec setup.

[Unreleased]: https://github.com/talmolab/sleap-roots-training/compare/v0.0.1a0...HEAD
[0.0.1a0]: https://github.com/talmolab/sleap-roots-training/releases/tag/v0.0.1a0
