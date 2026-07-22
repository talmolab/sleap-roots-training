# Proposal: Add typed OmegaConf training-config schema + `validate` CLI

## Why

The pipeline is config-driven, replacing the old notebook workflow: every experiment should be a
reproducible configuration file, not copy-pasted notebook cells. Before any training/evaluation
tier, we need a typed, validated configuration foundation so configs fail fast with clear errors
and downstream tiers build on a stable contract. This also seeds the spec-driven (OpenSpec)
workflow for the repo.

## What Changes

- Add a typed **OmegaConf structured config** (`sleap_roots_training.config`) covering the core
  experiment fields (dataset, model/backbone, training, and output/W&B), with sensible defaults
  and structured validation.
- Add a `sleap-roots-training validate <config.yaml>` CLI subcommand that loads a config file,
  merges it onto the schema, validates types and required fields, and reports a clear pass/fail
  with an appropriate exit code.
- Include a **Weights & Biases logging configuration** in the schema whose default enables
  **per-epoch** metric logging, so Tier-1 runs log per-epoch train/val loss and the stopping epoch
  (closing the observability gap the legacy TF reference runs exposed — see `docs/tf-reference.md`
  and `docs/roadmap.md` Tier 1; recorded here per issue #8).

## Impact

- **Affected specs:** `training-config` (ADDED).
- **Affected code:** `src/sleap_roots_training/config.py` (new); `src/sleap_roots_training/cli.py`
  (add `validate` subcommand); `tests/`; an example config; `docs/CHANGELOG.md`.
- **Breaking changes:** none (new repository).
