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
- **Label root-type vocabulary expanded** to include `seminal` (wheat's root type, not in the
  model-side `_ROOT_SLOTS`). Labels are a superset of model root types — a label set can describe
  a root type no model has been trained for yet.
- **New normalized collection names** following the model registry's `species-mode-root_type`
  pattern. Existing artifact versions are linked into the new collections (not re-published), so
  nothing already consumed by a training run is orphaned.
- **Provenance reconstruction** from artifact `description` free text, the lab share, and Bloom.
  Unrecoverable fields are `null` — no values are fabricated.
- **Single-species verification** for each collection before stamping it with a `LabelCard`.

## Impact

- **New spec:** `specs/label-registry/spec.md`
- **Affected code:**
  - `src/sleap_roots_training/labeling/metadata.py` — `ROOT_TYPE_VOCAB` expanded to include
    `seminal`
  - New `src/sleap_roots_training/registry/label_cards.py` — `LabelCard` backfill logic
    (provenance mapping, collection naming, metadata construction)
  - New `src/sleap_roots_training/registry/label_publish.py` — publish/link backfilled cards to
    the labels registry
  - `src/sleap_roots_training/cli.py` — new `seed-label-registry` subcommand
- **Affected tests:** new `tests/test_registry_label_cards.py`,
  `tests/test_registry_label_publish.py`
- **External:** reads from `wandb-registry-sleap-roots-labels` (existing); writes normalized
  collections back to the same registry. `sleap-roots-predict`'s parity harness is a downstream
  consumer.
- **Blocked by:** #10 (`LabelCard` contract — shipped)
- **Blocks:** Tier 2.2 (per-model parity), Tier 2.7 (skeleton unification), Tier 3 (generalist
  sweeps)
