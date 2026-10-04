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
+ GPU install). For config-driven training + evaluation (authoring a config, `validate`, running
a model, reading results), see [docs/training.md](docs/training.md).

## Seeding the production model registry

`sleap-roots-training seed-registry` publishes the root models named in the committed
`src/sleap_roots_training/registry/data/model_selection.yaml` into a Weights & Biases
registry as `type="model"` artifacts, each stamped with `ModelCard` selection metadata and
linked under the configured alias (default `production` — the exact surface the
`sleap-roots-predict` warm worker reads). **One card describes one physical model**: a card carries a scalar
`root_type` plus a `selectors` list, one entry per `(species, mode, age_min, age_max)`
combination that model was validated for, so a model trained across several species is
published once rather than once per species.

### Configuration (environment)

| Variable | Purpose | Default |
|---|---|---|
| `WANDB_ENTITY` | wandb entity (also wandb-native — steers run placement) | `eberrigan-salk-institute-for-biological-studies` |
| `SLEAP_ROOTS_MODEL_REGISTRY` | **models** registry name (a separate `sleap-roots-labels` registry also exists) | `sleap-roots-models` |
| `SLEAP_ROOTS_MODEL_ALIAS` | the alias the seed links each card under. Stripped. Set but **blank is an error** for `seed-registry`, never the default (unlike the seed project below). | `production` |
| `SLEAP_ROOTS_SEED_PROJECT` | wandb project the seed run is created in, and so where every published **source** artifact lives (producer-only; the consumer reads the registry, never this project). Empty means the default. | `sleap-roots-training` |
| `WANDB_API_KEY` | one way to authenticate wandb-contacting operations; a `wandb login` session (netrc entry for `api.wandb.ai`) also satisfies the guard | — |

Defaults live in `registry/config.py`; the species/mode vocabulary lives in
`registry/chooser.py` — reference those rather than re-hardcoding.

**Cross-repo invariant:** `SLEAP_ROOTS_MODEL_REGISTRY` here must equal the consumer's
`SRP_WANDB_REGISTRY` (which has **no default** — the operator must set it), and the entity
default is shared with `SRP_WANDB_ENTITY` across both repos. The consumer reads its alias from
`SRP_WANDB_MODEL_ALIAS`, default `production` (`sleap_roots_predict/model_registry.py`), and no
deployment sets it — so production predict sees only `production`-aliased cards. Cards published
here under another alias (for example `candidate`) are invisible to production predict; parity and
trait checks read them by setting `SRP_WANDB_MODEL_ALIAS` to match. See
[Publishing under a non-default alias](#publishing-under-a-non-default-alias).

### Do not delete these wandb projects

A registry entry is a **link** to a source artifact, and the source lives in whichever wandb
project the seed run used. Before `SLEAP_ROOTS_SEED_PROJECT` existed, wandb named that project
after the git checkout's directory (a worktree name, here), so two folder-named projects under
`eberrigan-salk-institute-for-biological-studies` now hold live sources:

| Project | Holds | If deleted |
|---|---|---|
| `migrate-model-card-selectors` | the sources of all 8 `production` links (verified 2026-09-30) | every production link breaks, and prediction with it |
| `sleap-roots-training-talmolab` | the sources of the 13 flat collections retired on 2026-09-29 (#68) | the rollback of that retirement becomes impossible |
| `sleap-roots-training` | every seed since the pin, including the wheat and sorghum `candidate` sources (#72), which become `production` sources when promoted | their candidate links break now, and their production links after promotion |

**Do not delete or "clean up" either project**, however disposable its name looks. The same
applies to the source artifact versions and seed runs inside them, and to the registry
collections themselves: deleting a collection is not recoverable. (The 13 retired flat
collections are now empty; a rollback re-links their sources into them.) New seeds go to
`sleap-roots-training`. Existing sources are deliberately not moved: re-linking them could
change registry versions, and the downstream idempotency key hashes
`(registry_id, version, weights_checksum)`.

**Do not `--force` an existing collection unless you intend a new version.** Because new seeds
log into `sleap-roots-training`, not the project holding the current source, a forced re-seed of
unchanged weights is expected to add a new registry version (for example `v1`) rather than being
de-duplicated. That would change every scan's idempotency key and recompute it once. This is
inferred from how wandb keys artifact sequences per project, not yet observed.

### Usage

```bash
# Dry run (default): print the plan + resolve every model, no wandb.
sleap-roots-training seed-registry --models-root <models-root>

# Publish (checks WANDB_API_KEY, then confirms the target unless --yes). A collection that
# has never carried `production` needs --only <id> --promote (see Rerun contract).
sleap-roots-training seed-registry --models-root <models-root> --execute

# Verify the live registry (read-only; no --models-root needed).
sleap-roots-training seed-registry --verify
```

The command's first line of output is the target: entity, registry, alias, whether the alias came
from `SLEAP_ROOTS_MODEL_ALIAS` or the default, and the seed project. Read it before trusting the rest.
(Option-parsing errors and `uv`'s own warnings can print before it.)

`--models-root` is a directory of `<source_model_id>.zip` archives — the models-downloader
snapshot for most models, but any directory laid out that way works (the wheat model ships in no
snapshot). Each archive is SHA256-verified against the matrix's `checksums`, then extracted
(OS-junk filtered) so the published `weights_checksum` is deterministic.

### Rerun contract

Re-running is safe: a card whose collection already carries the **configured** alias is
**skipped** (so a re-run resumes after a partial failure). The skip is per alias: a collection
carrying only `candidate` is *not* skipped by a `production` run. Moving the alias to a new
version requires `--force`. **Caution:** `--execute --yes` publishes non-interactively — do not
bake it into shared automation.

**A first-time `production` link needs `--promote`.** Under the default alias, `--execute` first
checks, read-only, which in-scope collections have never carried `production`, and refuses them
(exit 1) unless `--promote` is given. `--promote` requires `--only`, so a promotion always names
its collections. This holds under `--force` too. Consequences:

- While any matrix card is unpromoted (for example a `candidate` card awaiting its gates), a full
  default-alias `--execute` is refused. Re-seed the promoted ones with `--only <their ids>`.
- A re-run after a partial promotion repeats the same `--only … --promote`.

**`--force` is not evidence that metadata was refreshed.** Artifact metadata is not part of
the manifest digest, so re-logging byte-identical weights creates no new version and can
leave the previously published metadata live. The seed therefore reads the server's own view
back after linking and, where the metadata is stale, refreshes it in place; a collection that
still does not take is reported in a distinct `failed` bucket and exits non-zero, with the
remaining cards still attempted. Use that report, not the presence of `--force`, to decide
whether a collection is migrated.

### Rollout (canary-first)

The consumer reads with an older wandb than the producer writes with, so seed **canary-first**:
`--only <collection_id> --promote` publishes a single card, run the consumer's `pytest -m wandb`
on it, then `--only <canary> --only <each remaining id> --promote` seeds the rest (skipping the
canary).

`--only` scopes the expected set before it is computed, so **`--verify --only <id>` suppresses
orphan reporting** and says so in its output — every collection outside the scope would
otherwise be reported as orphaned. Run a full `--verify` (no `--only`) for the orphan report.

### Publishing under a non-default alias

To put cards in the registry without making them live — for example the wheat and sorghum cards
awaiting parity and trait checks (#72) — publish under another alias:

```bash
SLEAP_ROOTS_MODEL_ALIAS=candidate sleap-roots-training seed-registry \
  --models-root <models-root> --only <id> [--only <id> ...] --execute
```

In PowerShell, set it for the session with `$env:SLEAP_ROOTS_MODEL_ALIAS = 'candidate'` and remove it
afterwards with `Remove-Item Env:SLEAP_ROOTS_MODEL_ALIAS`. Check the target line either way.

- **`--only` is required.** Under a non-default alias no card counts as seeded, so an unscoped
  `--execute` would re-publish every card in the matrix; it is refused (exit 2).
- **Verify under the same alias:** `SLEAP_ROOTS_MODEL_ALIAS=candidate … --verify --only <ids>`.
- **A default `--verify` reports those cards `missing` and exits 1** until they are promoted. That
  is the expected state — read the missing list, do not ignore the exit code.
- **If the alias variable is lost,** the same command runs under `production` and the promotion
  check refuses it (those collections have never carried `production`).
- **Promote** later with the default alias: `--only <ids> --promote --execute`, from the same seed
  project and the same staged archives, then confirm on read-back that no new version was made.
- **Roll back** a card by fetching its registry link, asserting `is_link`, and calling `unlink()`.
  Never `save()` the source artifact: it reports success and leaves the alias live.

### W&B compatibility

Tested pair: **producer `wandb 0.28.x` ↔ consumer `wandb 0.21.3`**, canary-verified. The
producer pins `wandb>=0.28.0,<0.29.0`; **raising that cap requires a re-canary** and a
consumer floor bump. The two repos are intentionally *not* version-locked — they exchange
through the server-side registry, and the canary is the compatibility evidence.

### Notes for downstream consumers

- **Age windows are inclusive, and the oldest one stretches.** A scan older than its species'
  highest `age_max` is matched at that maximum, with a warning; a scan younger than every window
  gets no model. So a 17-DAG sorghum scan selects the 3–14 cards, and a 2-DAG one gets none.
- **Wheat `crown` is the team's name for seminal roots**, so wheat crown traits describe seminal
  roots. The wheat crown model was trained on wheat seminal + rice crown labels.

- Seeded `mode` strings are a selection contract: arabidopsis has two cylinder-family modes
  (`cylinder` vs `multiplant cylinder`) mapping to different models, so callers must emit the
  exact string.
- A model shared across species is published **once**, as a single artifact whose card lists
  one selector per validated `(species, mode, age_min, age_max)` combination. Match on the
  **any-selector** rule — a card matches a request when *some single* selector matches all of
  species, mode, and age — never on the cross product of its axes, which would advertise
  combinations nobody trained.
- Read a scan's age against the **matching selector's** window, never a card-level minimum or
  maximum. There is no card-level age bound, and inventing one from the union widens coverage:
  the shared primary-root card spans 2–13 for canola and 2–14 for the others, and advertises
  neither globally.

## Taking inventory of the label corpus

Nobody had ever enumerated what labeled data exists. The registry holds 8 collections against an
expected 25–30, and `skeletons.yaml` cannot express the corpus it claims to describe.

```bash
# Walk a share root, read each labels file, and write a table and a report under inventory/.
uv run sleap-roots-training inventory labels "Z:/users/<you>/SLEAP"

# Skip the registry digest check (no credential needed).
uv run sleap-roots-training inventory labels "Z:/users/<you>/SLEAP" --no-registry
```

The first scan's (#58) headline finding was that `skeletons.yaml` had no `mode`, so a 6-node
cylinder arabidopsis primary family and an 8-node plate one selected the same row. The table now
carries a mode, and the report lists the capture modes observed with no row of their own and the
node counts that disagree with their row. Node counts are read from the files, so none of this
needs an external service. The committed `inventory/label-inventory.md` predates the mode key and
still shows the old finding until the next scan.

Two things to know before reading the output. `species`, `mode` and `root_type` are **name-derived**
— read off the path, not out of the file — and the report says so; they are not evidence. And where
the tool cannot tell which files form a collection, it lists them and **makes no determination**.
A directory is not a collection: one on the measured share holds 28 labels files spanning a
superset, a second species' collection, a generalist, per-labeler inputs and practice files.
Deciding is a person's job, and there is deliberately nowhere to record the answer.

Every emitted path is relative to the supplied root, which appears as `<ROOT>`, and a referenced
video path is emitted as its filename alone — nothing above the root reaches an artifact.

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
