# Proposal: A re-runnable label-corpus inventory

## Why

Nobody has enumerated what labeled data actually exists. Every table in this program was
seeded from a snapshot of *deployed* state, and each snapshot's omissions silently became
the schema — so `wandb-registry-sleap-roots-labels` holds **8** collections against an
expected corpus of roughly 25–30, and `skeletons.yaml` cannot even express two of the
eight because it has no `mode` key.

## Background

Three independent sources describe the same corpus and none of them has been reconciled
against the others:

- **The registry.** 8 collections. Six carry a `v1` that is a *"Re-embedded
  (referenced_videos) repair … to restore trainable images"*; `v1` drops every species tag
  and records a throwaway temp `data_path`, while `v0` holds the real path and the species
  metadata. The two soybean collections were uploaded as `.pkg.slp` with images already
  embedded and have no `v1`.
- **The share.** `Z:` is `hpi_dev`. All eight recorded source paths — across three
  different prefixes (`D:/SLEAP/…`, `//multilab-na.ad.salk.edu/hpi_dev/…`,
  `Z:/users/…`) — map onto one tree, and every one resolves and size-matches its registry
  copy. `sleap-roots-training#49` currently records these paths as unusable; that
  assessment reads `v1`.
- **Bloom.** `bloomctl`'s `scan_relative_dir` builds
  `images/Wave{n}/Day{day}_{date}/{qr}`, and legacy video paths are
  `…/Day14_2-7-2025FastScanner/A2R61V978O.h5`. The 10-char code is `qr_code`, so
  `cyl_scans_extended` is joinable and supplies `species_name`, `plant_id` and
  `plant_age_days` per scan — the facts the other two sources only imply.

Full design and the resolved decisions are in
[`docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md`](../../../docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md).

## What Changes

**Additive. No existing capability, table, or shipped code path changes.**

Add a **label-inventory** capability: a re-runnable command that resolves each collection
to a digest-verified local file, derives per-scan facts independently from the labels file
and from Bloom, reconciles the two, and emits three artifacts.

```
sleap-roots-training inventory labels --out inventory/
```

Deriving from two sources and requiring them to agree is the point. Filename parsing gives
a *guess* at species (a folder called `SLEAP_wheat`) and a *proxy* for plants (deduped QR
codes). Bloom gives `species_name` and `plant_id` from the system of record. Where they
agree the value is evidenced; where they disagree it is a flagged row for a human, never a
silent pick.

### Deliverables

- **Per-scan CSV, one per collection.** One row per video, columns grouped by which source
  produced them. Bloom-derived column names match `bloomctl`'s `CSV_COLUMNS` exactly, so
  these join to `scans.csv` and to new-package manifests without translation.
- **Aggregate YAML, all collections.** The `LabelCard` fields, per-field confidence, and
  the reconciliation tally. Consumed directly by `#49`'s §2.
- **`skeletons.yaml` diff.** Which rows each collection verifies, contradicts, or is
  missing — including the `mode`-keying gap.

## Non-goals

- **Writing anywhere.** `bloomctl cyl` exposes `ingest` and the registry accepts publishes;
  this capability performs neither. Enforced normatively, not by convention.
- **Fixing what it finds.** `skeletons.yaml`'s missing `mode` key and absent species rows,
  `#3`'s deferred plate models, and the `RootType` gap for tip models are each a separate
  change. This capability reports.
- **The model inventory.** A second change, sharing the share walk but feeding `#3` and
  the roadmap rather than `#49`.
- **Train/test splits.** The unit is the superset labels file per collection;
  `train_test_split.vNNN/` describes a training run, not a corpus.

## Impact

- **Affected specs:** new **`label-inventory`** capability (ADDED). ADDED rather than
  MODIFIED deliberately: no live spec covers label provenance — `label-registry` belongs
  to in-flight `#49` and is not on `main`, so a MODIFIED block would re-paste a spec that
  does not exist yet. Precedent: `add-tf-reference-fixtures` added `tf-reference` the same
  way.
- **Affected code:** new `src/sleap_roots_training/inventory/` (`resolve.py`, `read.py`,
  `bloom.py`, `reconcile.py`, `emit.py`), and one `inventory` command group in `cli.py`.
  Kept out of `registry/` and `labeling/`, both of which have in-flight changes
  (`labeling-package` ×2).
- **Affected tests:** new `tests/test_inventory_*.py`. No existing test changes.
- **Affected docs:** `docs/CHANGELOG.md`, and a new `docs/inventory.md` describing how to
  re-run it and what the artifacts mean.
- **Not touched:** `skeletons.yaml`, `model_selection.yaml`, `chooser.py`,
  `SPECIES_VOCAB`, `registry/`, `labeling/`, and `#49`'s change directory.
- **New dependency:** none. `sleap-io` and `wandb` are already required; Bloom is reached
  through its documented REST surface behind an injectable client.
- **Requires:** the `Z:` share, `WANDB_API_KEY`, and `~/.bloom/credentials.txt` (profile
  `prod`, read-only). Absent any of these the command degrades per-source rather than
  failing wholesale.
