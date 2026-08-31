# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Pinned `sleap-roots-contracts` to `0.1.0a8` and **reshaped the registry so one card describes one
  physical model** (#39). A card now carries a scalar `root_type` plus a `selectors` list — one
  entry per `(species, mode, age_min, age_max)` combination the weights were validated for —
  instead of one card per matrix row. Expansion groups by `(source_model_id, root_type)`, so the
  committed 7-row matrix yields **8 cards over 8 physical models** rather than 13, and a generalist
  model (one primary-root model already serves arabidopsis/canola/pennycress) is editable in one
  place. Selectors are de-duplicated and sorted on an explicit key, so emitted metadata is
  byte-identical across processes and independent of matrix row order. Matching is the
  **any-selector** rule — some single selector must match all of species, mode, and age — never the
  cross product, which would advertise combinations nobody trained.

  **For registry operators:** this is **breaking, and it renames every live collection.** Collection
  ids are now derived from `source_model_id` (each `/` and `=` replaced with `-`) rather than built
  from the selection tuple, because a card with several species has no single species to name itself
  after. The re-seed is therefore purely **additive**: it creates 8 new collections and leaves the 13
  existing ones untouched, so `--verify` reports those 13 as orphans until they are retired. There is
  deliberately **no tolerant read** of the old flat shape — an upgraded consumer skips old-shape
  cards with a warning and an old-pinned consumer skips the new ones, which cleanly partitions the
  two generations during the migration instead of producing two matching cards for one context.
  **Order matters:** re-seed and verify here first, then deploy the upgraded `sleap-roots-predict`,
  and only retire the old collections once that deployment is confirmed. Publishing also now reads
  the server's own metadata back after linking and refreshes it in place when stale — `--force`
  alone does not create a new version when the weights digest is unchanged, so it is not evidence
  that metadata was refreshed.
- Pinned `sleap-roots-contracts` to `0.1.0a6` (from `0.1.0a3`) and **collapsed the local mode
  vocabulary into the contract-owned `Mode`**. `chooser.MODE_VOCAB` is now derived from
  `sleap_roots_contracts.Mode` rather than restated here, so the producer and the
  `sleap-roots-predict` consumer agree by construction instead of by reconciliation at acceptance.
  `SPECIES_VOCAB` stays local — a *selector's* `species` is a free `str`, so there is no
  contract-side species vocabulary to defer to. **Nothing accepted or published changes:** the contract's `Mode`
  is set-identical to the vocabulary it replaces, and all 7 rows of the committed selection matrix
  are already in vocabulary, so no card that validated before stops validating and no config that
  validated before stops validating. Two *error-reporting* surfaces did change, both noted below.
  Upstream, `0.1.0a6` is
  a breaking *validation* tightening (the card's `mode` is a `Mode` and no longer a free `str` —
  it lives on `Selector` as of the `0.1.0a8` reshape below;
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
- Tier 1 PyTorch-native baseline (#21): the config-driven path (`validate → emit → sleap-nn train`)
  run on the exact original v000 held-out split (Arabidopsis primary-root, multi-plant cylinder,
  bottom-up). Reported as a 3-seed range (42/43/44) on val for the stable `output_stride 4` config:
  `dist_avg` **30.1–37.8 px**, `dist_p50` **17.7–21.2 px**, `vis_recall` **0.85–0.91** (all
  instances detected), with per-epoch W&B logging confirmed. The TF reference is shown alongside as
  context only, not a gate. (**Corrected 2026-08-06:** the TF W&B `dist_*` values are
  **millimeters** from a lab post-processing step, so the earlier "20–40× gap" reading was a unit
  error. In pixels the two backends are comparable, and the PyTorch baseline detects 44/44 instances
  on every seed where no TF run exceeds 43/44 (on `vis_recall`, two of its three seeds clear TF's
  best of 0.872 and seed 43 does not); sleap-nn's evaluator also reproduces SLEAP's own metrics
  exactly. See
  `docs/tf-reference.md`.) Documented finding: the finer `output_stride 2` collapses to zero predictions
  on 2 of 3 seeds at `confmaps.sigma 2.5`; a `sigma` ablation (`sigma 5.0` trains stably on all 3
  seeds) shows the cause is too-tight confmap targets, not a resolution ceiling or the loss — so the
  baseline stays `output_stride 4`. Adds `examples/baseline_bottomup_v000_os4.yaml` +
  `..._os2.yaml` + `..._os2_sigma5.yaml` (the ablation), `scripts/clean_pkg.py` (make the v000
  `.pkg.slp` self-contained for the offline GPU box), and `scripts/dump_val_metrics.py`; write-up in
  `docs/training.md` ("PyTorch baseline").
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
  `pandas.sample` — which is what makes widening the plant dimension produce a superset instead
  of a different label set; view indices are unchanged (`[1, 25, 49]` for three), but curated
  filenames now name the **view** rather than its position in the selection
  (`..._age3_view025.jpg`, not `..._age3_0.jpg`), so a filename means the same image at every
  selection width; skeletons come from a committed per-crop table and an uncovered crop **fails**
  instead of getting soybean's node counts; and every silent failure is now a failure — an
  unresolvable source image, an absolute or `..`-bearing source path, a duplicate or
  case-colliding curated filename, a curated filename that is not a plain filename, a scan whose
  view count contradicts `--total-views`, a scan with no predictions, a scan whose predictions do not cover every
  selected view, a null `accession_id` or `plant_age_days`, and an empty
  selection each stop the run rather than warning and reporting success. `labeling validate`
  opens each `.slp` and counts its frames rather than checking the declared count against the
  manifest it came from. A frame the model found nothing in ships **empty** rather than vanishing,
  so a labeler can confirm a true negative — the corpus previously had no way to record one, and
  genuine absence was indistinguishable from predictions that missed the view. `labeling validate` and ignores operating-system sidecars so a `.DS_Store` cannot fail a
  correct package. `package_metadata.yaml` also records a `provenance` block — the input hashes,
  the skeleton-table hash, and the code version — because the selection parameters alone only
  reproduce a package against a byte-identical pool. Adding frames to a published package is
  re-derive and republish, not edit in place; the reason is in the guide.
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
  artifacts with `ModelCard` selection metadata and the `production` alias — the
  surface the `sleap-roots-predict` warm worker reads. Defaults to a dry run; `--execute`
  (with `--yes`/`--force`/`--only`) publishes; `--verify` re-runs the consumer read path,
  reports collections the matrix no longer produces, and fails on a stale metadata shape.
- `sleap_roots_training.registry` package: env-driven config, the provenance-stamped
  `model_selection.yaml` (7 rows → 8 cards, one per SHA256-pinned physical model), card expansion,
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

### Fixed
- `scripts/dump_val_metrics.py` no longer aborts the whole batch on one corrupt `.npz` (#52). Its
  handler caught `(OSError, ValueError, EOFError, zipfile.BadZipFile)`, but numpy ≥ 2 raises
  `pickle.UnpicklingError`, which subclasses none of them — so the handler stopped firing and a
  single unreadable file killed the run. **Runs listed after a corrupt one were silently never
  dumped**, defeating both the guarantee the handler's comment claims and `main`'s deliberate
  list-materialization. Older numpy raised `OSError` here, so this is numpy's error surface moving
  underneath a closed type list rather than a mistake at the time of writing.

  The fix separates reading from formatting: the file read is guarded by `except Exception` and
  the `_emit` formatting sits outside it. Both halves are load-bearing. `np.load` returns a *lazy*
  `NpzFile` whose members are unpickled on access, so guarding `np.load` alone would still miss a
  well-formed archive holding a truncated pickle — the shape an interrupted `sleap-nn train`
  actually produces, and the likelier failure of the two. Keeping `_emit` outside the guard means a
  bug in our own formatting crashes loudly instead of being reported to the operator as
  `CORRUPT (<path>)`, sending them to investigate a data file that is fine.

  **These tests now run in CI.** They were marked `integration` "so they run only where the train
  extra is installed", but `numpy` is an unconditional requirement of both `pandas` and `sleap-io`,
  which are *core* dependencies — so the premise was false and the marker only meant the tests ran
  nowhere (CI runs `-m "not integration"`). That is why the bug survived on `main` with a green
  badge and a test that caught it. The marker is removed; #53 tracks the 5 integration tests still
  in that position.

## [0.0.1a0] - 2026-06-24

### Added
- Initial repository scaffold: package skeleton, CLI entry point
  (`sleap-roots-training --help`), test suite, CI, and OpenSpec setup.

[Unreleased]: https://github.com/talmolab/sleap-roots-training/compare/v0.0.1a0...HEAD
[0.0.1a0]: https://github.com/talmolab/sleap-roots-training/releases/tag/v0.0.1a0
