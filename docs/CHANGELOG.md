# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
