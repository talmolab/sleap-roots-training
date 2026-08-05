# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Pinned `sleap-roots-contracts` to `0.1.0a6` (from `0.1.0a3`) and **collapsed the local mode
  vocabulary into the contract-owned `Mode`**. `chooser.MODE_VOCAB` is now derived from
  `sleap_roots_contracts.Mode` rather than restated here, so the producer and the
  `sleap-roots-predict` consumer agree by construction instead of by reconciliation at acceptance.
  `SPECIES_VOCAB` stays local — `ModelCard.species` is a free `str`, so there is no contract-side
  species vocabulary to defer to. **Nothing accepted or published changes:** the contract's `Mode`
  is set-identical to the vocabulary it replaces, and all 7 rows of the committed selection matrix
  are already in vocabulary, so no card that validated before stops validating and no config that
  validated before stops validating. Two *error-reporting* surfaces did change, both noted below.
  Upstream, `0.1.0a6` is
  a breaking *validation* tightening (`ModelCard.mode` is a `Mode` and no longer a free `str`;
  `age_min`/`age_max` reject `bool` and `numpy.bool_`) — neither reaches anything this package
  produces. This also unblocks `add-label-registry` (#10), which needs `LabelCard`.

  **For config authors:** `MODE_VOCAB` also backs `validate`'s check on the hand-written
  `experiment.mode`, so the contract now governs a user-facing config field and not only published
  metadata. A future `sleap-roots-contracts` release that *narrows* `Mode` would therefore reject a
  `mode:` you have already written. The three authoring surfaces are guarded in CI — the committed
  selection matrix, the shipped `examples/`, and every `mode:` documented in `docs/training.md` — so
  a narrowing fails at bump time here rather than in your config. Modes are matched **exactly** at
  every surface (no case or whitespace normalization — `Cylinder` and `multiplant-cylinder` are
  errors, as before); a near miss now gets a "did you mean" hint on the error, never a silent
  correction. The hint comes from a shared helper, so it also applies to `experiment.species` and
  `experiment.root_type`. Rationale and the full `a3 → a6` delta review are in the change's
  `design.md`.

  **For registry operators:** `seed-registry` now reports a rejected selection matrix as a clean
  `Error: ...` instead of an unhandled traceback — out-of-vocabulary `species`/`mode` and a
  non-contiguous `age` carry the loader's row-numbered message unchanged, and a file that cannot be
  loaded at all (a directory, invalid YAML, or YAML whose top level is not a mapping) now names the
  path and what was wrong with it. Same failures, same messages — only the packaging changed.
  `--selection-matrix` also rejects a directory at the argument itself rather than failing later
  inside the loader.

  **Cold-start cost:** this is the first code path in the package that actually imports
  `sleap_roots_contracts` (and transitively `pydantic`) rather than only reading its version, and
  `chooser` is on the CLI's import path — so `--help`, `--version` and every shell TAB-completion
  press pay it, not just `train` / `seed-registry`. Measured at **+72–87 ms** (machine-dependent;
  an earlier draft of this entry said ~183 ms, which was `chooser`'s total import cost rather than
  what this change adds). Immaterial next to a training run, but noted because it departs from the
  lazy-import convention this repo uses for `wandb` and `sleap-nn`.
- The wandb credential guard (`seed-registry --execute` / `--verify`) now accepts a resolvable
  wandb credential — `WANDB_API_KEY` **or** a netrc entry for `api.wandb.ai` written by
  `wandb login` — instead of requiring `WANDB_API_KEY`. The netrc file is located the way wandb
  locates it (`NETRC` env var, else `~/.netrc`, else `~/_netrc`), so a login session is honored on
  every platform (including Windows `~/_netrc`). Fail-fast with a clear error is retained when no
  credential is resolvable anywhere; a malformed netrc — or a netrc entry with a blank/absent
  password — is treated as "no credential" (mirroring wandb's own resolver), so a stale login fails
  before the confirmation prompt rather than deep inside `wandb.init()`.

### Added
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
