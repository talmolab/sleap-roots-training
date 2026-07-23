# sleap-roots-training

Config-driven training and evaluation of [SLEAP](https://sleap.ai) root models on the
[`sleap-nn`](https://github.com/talmolab/sleap-nn) backend, with
[Weights & Biases](https://wandb.ai) experiment tracking and Run:AI for compute.

This package replaces the notebook-based `eberrigan/sleap-roots-training` workflow with a
reproducible, tested, OmegaConf-driven pipeline. It is built out tier by tier following the
program roadmap (generalist + per-crop keypoint models → segmentation masks).

## Status

Early scaffold (alpha). The pipeline is being implemented incrementally — see
`openspec/` for in-progress changes and `docs/CHANGELOG.md` for releases. The program plan is in
[`docs/roadmap.md`](docs/roadmap.md); the TensorFlow reference baseline is documented in
[`docs/tf-reference.md`](docs/tf-reference.md).

## Install (development)

```bash
uv sync --group dev
uv run sleap-roots-training --help
```

To install the optional `sleap-nn` keypoint training backend and run/predict a model, see
[docs/training-backend.md](docs/training-backend.md) (the `sleap-roots-training[train]` extra
+ GPU install).

## Seeding the production model registry

`sleap-roots-training seed-registry` publishes the current legacy root models (from the
committed `src/sleap_roots_training/registry/data/model_selection.yaml`) into a Weights &
Biases registry as `type="model"` artifacts, each stamped with flat `ModelCard` selection
metadata and the `production` alias — the exact surface the `sleap-roots-predict` warm
worker reads.

### Configuration (environment)

| Variable | Purpose | Default |
|---|---|---|
| `WANDB_ENTITY` | wandb entity (also wandb-native — steers run placement) | `eberrigan-salk-institute-for-biological-studies` |
| `SLEAP_ROOTS_MODEL_REGISTRY` | **models** registry name (a separate `sleap-roots-labels` registry also exists) | `sleap-roots-models` |
| `SLEAP_ROOTS_MODEL_ALIAS` | alias marking a version production | `production` |
| `WANDB_API_KEY` | one way to authenticate wandb-contacting operations; a `wandb login` session (netrc entry for `api.wandb.ai`) also satisfies the guard | — |

Defaults live in `registry/config.py`; the species/mode vocabulary lives in
`registry/chooser.py` — reference those rather than re-hardcoding.

**Cross-repo invariant:** `SLEAP_ROOTS_MODEL_REGISTRY` here must equal the consumer's
`SRP_WANDB_REGISTRY` (which has **no default** — the operator must set it), and the entity
default is shared with `SRP_WANDB_ENTITY` across both repos. The consumer **hardcodes** the
`production` alias, so `SLEAP_ROOTS_MODEL_ALIAS` must remain `production` (a non-default alias would
be silently skipped by the consumer, and the producer's own `--verify` — which checks the same
configured alias — could not detect the skew).

### Usage

```bash
# Dry run (default): print the plan + resolve every model, no wandb.
sleap-roots-training seed-registry --models-root <snapshot-dir>

# Publish (checks WANDB_API_KEY, then confirms the target unless --yes).
sleap-roots-training seed-registry --models-root <snapshot-dir> --execute

# Verify the live registry (read-only; no --models-root needed).
sleap-roots-training seed-registry --verify
```

`--models-root` holds the `models-downloader` snapshot as `<model_id>.zip` archives; each is
SHA256-verified against the matrix, then extracted (OS-junk filtered) so the published
`weights_checksum` is deterministic for the snapshot.

### Rerun contract

Re-running is safe: a card whose collection already carries the `production` alias is
**skipped** (so a re-run resumes after a partial failure). Moving the alias to a new version
requires `--force`. **Caution:** `--execute --yes` publishes non-interactively — do not bake
it into shared automation.

### Rollout (canary-first)

The consumer reads with an older wandb than the producer writes with, so seed **canary-first**:
`--only <collection_id>` publishes a single card, run the consumer's `pytest -m wandb` on it,
then a full `--execute` seeds the rest (skipping the canary).

### W&B compatibility

Tested pair: **producer `wandb 0.28.x` ↔ consumer `wandb 0.21.3`**, canary-verified. The
producer pins `wandb>=0.28.0,<0.29.0`; **raising that cap requires a re-canary** and a
consumer floor bump. The two repos are intentionally *not* version-locked — they exchange
through the server-side registry, and the canary is the compatibility evidence.

### Notes for downstream consumers

- Seeded `mode` strings are a selection contract: arabidopsis has two cylinder-family modes
  (`cylinder` vs `multiplant cylinder`) mapping to different models, so callers must emit the
  exact string.
- A model shared across species is published as one artifact per species (distinct
  `registry_id`s), so a warm cache may materialize shared weights more than once — a known,
  accepted trade-off (predict-side dedupe by `weights_checksum` is a follow-up).

## Development

This repo follows the Talmo lab conventions (uv, ruff/black/pytest, OpenSpec, GitHub
Actions CI). Common tasks are available as Claude Code dev commands in `.claude/commands/`.

```bash
uv run black --check src/sleap_roots_training tests
uv run ruff check src/sleap_roots_training
uv run pytest
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
