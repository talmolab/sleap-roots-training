# Proposal: Seed the production model registry with the current legacy root models

## Why

`sleap-roots-predict` shipped a warm model worker (PR #9, branch `add-warm-model-worker`) whose
`WandbRegistrySource` fetches **production** root models from a Weights & Biases registry: it
lists model artifacts across the registry's collections, keeps only those carrying the
`production` alias, and validates each artifact's flat `metadata` against the `ModelCard` schema
from `sleap-roots-contracts`. Today that registry has no production content, so the consumer has
nothing to fetch.

This change **seeds** the registry with the real legacy TF/SLEAP root models currently used by the
`sleap-roots` pipeline (the models in `models-downloader`'s selection matrix), stamped with the
`ModelCard` selection metadata, aliased `production`, and linked into per-card collections. This is
**registry curation, not training** — the models already exist as legacy files; we upload them
as-is. Seeding now also establishes the exact **publishing surface** (metadata schema + `production`
alias + registry path) that this repo's future `sleap-nn`-trained models will reuse — the same
`ModelCard` contract whether weights are legacy or native.

## What Changes

- **Dependencies:** add `wandb` and `sleap-roots-contracts==0.1.0a3` as runtime deps; regenerate
  `uv.lock`.
- **Selection matrix (data):** commit a provenance-stamped **YAML** selection matrix
  (`registry/data/model_selection.yaml`) mirroring the current
  `models-downloader/model_chooser_table.xlsx` (20250204), read via OmegaConf.
- **Pure logic (unit-tested, no network):** parse the matrix and each row's `age` comma-list into a
  contiguous `age_min`/`age_max` window; expand each row into one card per non-empty root-type
  model, per species (so a model shared across species yields one card per species); map each card
  to flat `ModelCard`-valid metadata (`species`, `mode`, `age_min`, `age_max`, `root_type`, plus a
  non-contract `source_model_id` for traceability).
- **Model resolution (filesystem):** the canonical snapshot ships each model as a `<model_id>.zip`,
  so resolution verifies the archive against a **SHA256 recorded in the committed matrix** (pins the
  snapshot so the published `weights_checksum` is deterministic under the pinned wandb writer), then
  safely extracts it (junk-filtered) into a temp dir and confirms `best_model.h5` +
  `training_config.json`. Production writes (`--execute`) require the pinned archive form; an
  already-unzipped dir is a dev/dry-run-only convenience.
- **Registry integration (network):** env-driven config (entity/registry/alias) + wandb
  publish/link/alias helpers adapted from the old `eberrigan/sleap-roots-training` repo to the
  current wandb (0.28) API — publish each card as `Artifact(type="model", metadata=…)`, `add_dir`
  the whole model directory **as-is**, `log_artifact`, and link into a per-card collection under the
  registry with the `production` alias.
- **CLI:** add a `seed-registry` subcommand that **defaults to a dry run** (prints the planned
  collections + metadata and resolves every model directory, **without** contacting wandb) and
  requires an explicit `--execute` (checks `WANDB_API_KEY`, then confirms the target, bypassed by
  `--yes`) to publish — guarding a shared-registry write against an accidental run with
  `WANDB_API_KEY` already in the environment. Re-seeding is idempotent: a card whose collection
  already carries the `production` alias is skipped (moving the alias needs `--force`), so a re-run
  is a no-op and resumes after a partial failure. Producer lineage (git SHA + matrix date +
  tool/contract versions, via a wheel-safe resolver) is recorded in the **run config** — per-artifact
  metadata stays exactly the six selection keys.
- **Scope:** publishes the **8** legacy models present in the matrix → **13** production cards.

## Impact

- **Affected specs:** `model-registry` (ADDED).
- **Affected code:** new `src/sleap_roots_training/registry/` package (`__init__.py`, `config.py`,
  `chooser.py`, `cards.py`, `models.py`, `lineage.py`, `publish.py`) +
  `registry/data/model_selection.yaml`; `cli.py` (`seed-registry` subcommand); `pyproject.toml` +
  `uv.lock`; `.github/workflows/ci.yml` (add `--locked` to both `uv sync` steps + `uv.lock` to the
  `paths` filter); `tests/`; `docs/CHANGELOG.md`; README.
- **External:** seeds the eberrigan `sleap-roots-models` registry (env-overridable). After merge +
  a real seed run, `sleap-roots-predict` can flip its default source to the live registry
  (`SRP_WANDB_ENTITY` / `SRP_WANDB_REGISTRY` = the values used here). This task corresponds to the
  **A3-training "feeds model registry"** row in the *sleap-roots-pipeline* bloom-integration roadmap
  (`sleap-roots-pipeline/docs/bloom-integration/roadmap.md` — an external repo), with A3-predict =
  the consuming warm worker; those external rows update post-seed. It is **not** a tier in this
  repo's Tier-based `docs/roadmap.md` (which is scoped to sleap-nn training), so no edit to that file
  is in scope.
- **Deferred (out of scope):** the arabidopsis **plate** row (`arabidopsis_plates/primary` +
  `arabidopsis_plates/lateral`) — those model dirs are absent from the local `models-downloader`
  snapshot and the reference run, and have no concrete `.n=` id. Tracked by a follow-up GitHub issue;
  they slot into the same registry later with no schema change.
- **Breaking changes:** none (new capability in a new repo).
