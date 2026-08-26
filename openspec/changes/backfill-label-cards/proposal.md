## Why

The 8 existing label collections in `wandb-registry-sleap-roots-labels` cannot be joined to the
models trained on them. Six collections point at deleted temp directories; two at a `Z:` drive that
resolves on one machine. Collection names use `cyl` where models use `cylinder`, and naming
conventions differ (`mode_species_age_root` vs `species-mode-root-age`). Without `LabelCard`
metadata, no downstream consumer — training parity (Tier 2.2), generalist sweeps (Tier 3), or
skeleton unification (Tier 2.7) — can programmatically discover what a label set contains.

#10 shipped the `LabelCard` contract (`sleap-roots-contracts#24`). This change backfills the 8
existing collections onto that contract: reconstruct provenance, normalize naming, and verify
single-species content — so labels become queryable and joinable to models.

## What Changes

- **New `label-registry` spec capability** defining the `LabelCard` backfill contract: how
  existing collections are mapped onto `LabelCard`, what fields are nullable for legacy data, and
  how normalized collection names are derived.
- **New contract-owned `LabelRootType`** in `sleap-roots-contracts`, a superset of `RootType`
  adding `seminal` (wheat's root type). `LabelCard.root_type` is re-annotated to it;
  `ModelCard.root_type` and `RootType` itself are untouched. Labels are a superset of model root
  types — a label set can describe a root type no model has been trained for yet. This requires a
  contracts release; see design.md D3 for why widening `RootType` in place is not an option.
- **New label-side species vocabulary** (`LABEL_SPECIES_VOCAB`), a package-owned superset of
  `SPECIES_VOCAB` adding `wheat`, `sorghum`, and `medicago`. `SPECIES_VOCAB` is unchanged, so the
  model selection matrix and `experiment.species` in a training config keep accepting exactly what
  they accept today (D5).
- **New normalized collection names** following the model registry's `species-mode-root_type`
  pattern. Existing artifact versions are linked into the new collections (not re-published), so
  nothing already consumed by a training run is orphaned.
- **Provenance reconstruction** from artifact `description` free text, the lab share, and Bloom.
  Unrecoverable fields among the contract's seven `Optional` provenance fields are `null` — no
  values are fabricated. Four *required* fields (`age_min`, `age_max`, `n_plants`, `n_scans`) have
  no `null` available and are gated on archaeology; see D7.
- **Single-species verification** for each collection before stamping it with a `LabelCard`.

## Impact

- **New spec:** `specs/label-registry/spec.md`
- **Upstream:** `sleap-roots-contracts` release `0.1.0a9` — adds `LabelRootType`, and conditionally
  relaxes `age_min`/`age_max`/`n_plants`/`n_scans` to `Optional` if §2 archaeology cannot recover
  them (D7). The pin also catches up from `0.1.0a6` through `a7`/`a8`, which this repo has not yet
  absorbed; that bump follows the `archive/2026-08-05-update-contracts-pin-0-1-0a6` precedent.
- **Affected code:**
  - `src/sleap_roots_training/registry/chooser.py` — new `LABEL_ROOT_TYPE_VOCAB` (derived from the
    contract's `LabelRootType`, with the same import guard as `MODE_VOCAB`) and new
    `LABEL_SPECIES_VOCAB`
  - `src/sleap_roots_training/labeling/metadata.py` — `PackageMetadata` validates against the
    label-side vocabularies instead of the model-side ones
  - `src/sleap_roots_training/labeling/skeletons.py` — skeleton-table rows validate against the
    label-side vocabularies
  - New `src/sleap_roots_training/registry/label_cards.py` — `LabelCard` backfill logic
    (provenance mapping, collection naming, metadata construction)
  - New `src/sleap_roots_training/registry/label_publish.py` — publish/link backfilled cards to
    the labels registry
  - `src/sleap_roots_training/cli.py` — new `seed-label-registry` subcommand
  - **Not touched:** `registry/cards.py`'s `_ROOT_SLOTS`, `chooser.SPECIES_VOCAB`,
    `chooser.ROOT_TYPE_VOCAB`, and `config.py`'s `experiment` validation
- **Affected tests:** new `tests/test_registry_label_cards.py`,
  `tests/test_registry_label_publish.py`; updates to `tests/test_labeling_metadata.py` and
  `tests/test_labeling_skeletons.py` for the vocabulary split
- **External:** reads from `wandb-registry-sleap-roots-labels` (existing); writes normalized
  collections back to the same registry. `sleap-roots-predict`'s parity harness is a downstream
  consumer.
- **Blocked by:** #10 (`LabelCard` contract — shipped); #50 (root-type vocabulary collapse — D3 and
  D5 are written against the post-#50 layout); `sleap-roots-contracts` `0.1.0a9` (D3)
- **Blocks:** Tier 2.2 (per-model parity), Tier 2.7 (skeleton unification), Tier 3 (generalist
  sweeps)
