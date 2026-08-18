## Context

The `wandb-registry-sleap-roots-labels` registry holds 8 label collections published before the
`LabelCard` contract existed. Their metadata is ad hoc: boolean keys, free-text descriptions,
`data_path` fields pointing at deleted temp directories or a single-machine drive letter. The
`LabelCard` contract (`sleap-roots-contracts#24`, shipped via #10) gives labels the same structured
metadata models already have via `ModelCard` — but the existing 8 collections must be retrofitted
onto it.

### The 8 collections

| collection | species | mode | root_type | versions | data_path status |
|---|---|---|---|---|---|
| `soybean_lateral_4nodes_v007_labels` | soybean | cylinder | lateral | 1 | `Z:` drive |
| `soybean_primary_6nodes_v004_labels` | soybean | cylinder | primary | 1 | `Z:` drive |
| `plate_medicago_14DAG_primary_8nodes_labels` | medicago¹ | plate | primary | 2 | deleted temp |
| `plate_arabidopsis_2-7DAG_primary_8nodes_labels` | arabidopsis | plate | primary | 2 | deleted temp |
| `cyl_arabidopsis_7-11DAG_primary_6nodes_labels` | arabidopsis | cylinder | primary | 2 | deleted temp |
| `rice_3DAG_crown_6nodes_labels` | rice | cylinder | crown | 2 | deleted temp |
| `wheat_5-14DAG_seminal_6nodes_labels` | wheat | cylinder | seminal | 2 | deleted temp |
| `sorghum_5-12DAG_primary_6nodes_labels` | sorghum | cylinder | primary | 2 | deleted temp |

¹ `medicago` is not in the current `SPECIES_VOCAB`. Needs to be added or the collection excluded.

## Goals / Non-Goals

**Goals:**
- Stamp every collection with a valid `LabelCard` via normalized metadata
- Normalize collection names to match the model registry pattern (`species-mode-root_type`)
- Preserve existing artifact versions (link, don't re-publish)
- Expand root-type vocabulary to include `seminal`
- Verify single-species content per collection
- Mark unrecoverable provenance fields as `null`

**Non-Goals:**
- Recovering the deleted `data_path` files (the images live in the artifact blob)
- Building a `publish-labels` CLI for *new* packages (that is #10/#26 scope)
- Multi-species `LabelCard` support (decision: stays single-species)
- Changing the `ModelCard` side of the registry

## Decisions

### D1: Null for unrecoverable provenance, no `provenance: "reconstructed"` marker

`LabelCard` fields that cannot be recovered from the artifact description or Bloom are set to
`null`. The contract already permits `Optional` on provenance-class fields. A separate marker
type adds schema complexity without information — `null` already communicates "not recorded" and
is what `sleap-roots-predict`'s parity harness already uses for its interim `LabelCard` records.

### D2: New correctly-named collections, link existing versions

W&B collections cannot be renamed. Create new collections following the model registry's naming
convention (`species-mode-root_type`, e.g. `soybean-cylinder-lateral`), then link the existing
artifact versions into them. The old collections remain resolvable (nothing orphaned) but do not
carry the `production` alias — only the new ones do.

**Why link, not re-publish:** re-publishing creates new artifact digests, breaking any
`weights_checksum`-style references in downstream consumers. Linking preserves the original
artifact identity.

### D3: `seminal` added to label root-type vocabulary

The wheat collection uses root type `seminal`, which is not in the model-side `_ROOT_SLOTS`
(`primary`, `lateral`, `crown`). Labels describe what was annotated, not what models exist for.
`seminal` is added to `ROOT_TYPE_VOCAB` in `labeling/metadata.py` only — the model-side
`_ROOT_SLOTS` in `registry/cards.py` stays unchanged (no model exists for seminal roots). The
`LabelCard` contract's `RootType` in `sleap-roots-contracts` already includes `seminal` as a
valid value (confirmed).

### D4: Collection naming convention

Normalized names follow: `{species}-{mode}-{root_type}` with hyphens, matching the model
registry's convention. Age is omitted from label collection names — unlike models, which are
trained for specific age windows, a label set covers whatever ages were annotated and the age
range is metadata on the card, not part of the collection identity.

Examples:
- `soybean-cylinder-lateral` (was `soybean_lateral_4nodes_v007_labels`)
- `arabidopsis-cylinder-primary` (was `cyl_arabidopsis_7-11DAG_primary_6nodes_labels`)
- `wheat-cylinder-seminal` (was `wheat_5-14DAG_seminal_6nodes_labels`)

### D5: Species vocabulary expansion

`medicago` (from the plate medicago collection), `wheat`, and `sorghum` (from other collections)
are not in `SPECIES_VOCAB`. All three are added to `SPECIES_VOCAB` — they are real species with
published label data. `medicago` is confirmed in scope. This is the labels-side vocabulary — the
model-side vocabulary is a subset (only species with trained models).

### D6: Canary-first migration, matching `seed-registry --only` precedent

Migrate one collection first as a canary (verify the consumer can read the new-shape collection),
then migrate the rest. Same pattern `seed-registry --only` established for models.

## Risks / Trade-offs

- **Provenance gaps are real.** 6 of 8 collections have broken `data_path`. Free-text
  `description` may not contain enough to reconstruct `bloom_experiment_id` or accession IDs for
  all collections. These fields will be `null` and flagged.
- **`medicago`/`wheat`/`sorghum` vocabulary expansion** changes validation behavior for
  `PackageMetadata` — any code that expected the old vocabulary to be exhaustive will now accept
  more values. This is correct (the species exist) but is a behavior change.
- **Old collection names remain.** They are not deleted, only de-aliased. Consumers using the old
  names directly (not via `production` alias) will still resolve, but won't get `LabelCard`
  metadata.

## Open Questions

- **Q1:** Does the `LabelCard` contract in `sleap-roots-contracts` 0.1.0a6 allow `null` for
  `bloom_experiment_id`, `accessions`, and node-count fields, or does the schema need a bump?
  (Must verify before implementation.)
- ~~**Q2:** The medicago plate collection — is `medicago` a species this project will support
  long-term, or should it be excluded from the backfill and tracked separately?~~
  **Resolved:** `medicago` is in scope. Added to `SPECIES_VOCAB` alongside `wheat` and `sorghum`.
