## 0. Pre-implementation decisions (gate: all resolved before §1)

- [ ] 0.1 Verify `LabelCard` schema in `sleap-roots-contracts` 0.1.0a6 permits `null` for
      `bloom_experiment_id`, `accessions`, and skeleton/node-count fields. If not, determine
      whether a contracts bump is needed before this work can proceed.
- [x] 0.2 ~~Decide disposition of medicago~~ — **resolved:** `medicago` is in scope, added to
      `SPECIES_VOCAB` alongside `wheat` and `sorghum`.
- [ ] 0.3 Confirm `wheat`, `sorghum`, and `medicago` should be added to `SPECIES_VOCAB` (all
      three have published label data but no trained models). **`medicago` confirmed in scope.**

## 1. Vocabulary expansion

- [ ] 1.1 **Test:** add test asserting `seminal` is a valid label root type in `ROOT_TYPE_VOCAB`
      (red — currently not present).
- [ ] 1.2 Add `"seminal"` to `ROOT_TYPE_VOCAB` in `src/sleap_roots_training/labeling/metadata.py`
      (green).
- [ ] 1.3 **Test:** add test asserting new species (`wheat`, `sorghum`, `medicago`) are valid
      in `SPECIES_VOCAB` (red).
- [ ] 1.4 Add the new species to `SPECIES_VOCAB` in
      `src/sleap_roots_training/registry/chooser.py` (green). Document that the label-side
      vocabulary is a superset of the model-side vocabulary.
- [ ] 1.5 Confirm all existing tests still pass after vocabulary expansion (`pytest`).

## 2. Provenance reconstruction (archaeology)

- [ ] 2.1 For each of the 8 collections, pull the artifact from wandb and extract:
      - `description` free text
      - Existing metadata keys
      - Frame/video counts from the `.slp` or `.pkg.slp` blob
      - Any recoverable `bloom_experiment_id`, accession IDs, species confirmation
- [ ] 2.2 Record findings in a structured mapping (YAML or Python dict) per collection:
      which fields were recovered, which are `null`, and confidence level.
- [ ] 2.3 Verify single-species content: sample frames from each collection to confirm no
      mixed-species data. Record methodology and findings per collection.
- [ ] 2.4 For each collection, determine the node count per root type from the `.slp` skeleton.

## 3. LabelCard metadata construction

- [ ] 3.1 **Test:** for each of the 8 collections, a `LabelCard` can be constructed from the
      reconstructed metadata (null where unrecoverable) and validates against the contract.
- [ ] 3.2 Implement `label_cards.py`: a mapping from each old collection name to its
      `LabelCard` fields (species, mode, root_type, node_count, age range, provenance fields).
      Unrecoverable fields are explicitly `None`.
- [ ] 3.3 **Test:** the normalized collection name for each card follows the
      `{species}-{mode}-{root_type}` convention.
- [ ] 3.4 Implement `collection_id()` for label cards following D4's naming convention.
- [ ] 3.5 **Test:** no two cards produce the same collection id (uniqueness guard).
- [ ] 3.6 **Test:** every card's `mode` validates against `MODE_VOCAB` and every card's
      `species` validates against the (expanded) `SPECIES_VOCAB`.

## 4. Registry migration (publish + link)

- [ ] 4.1 **Test:** linking an existing artifact version into a new collection preserves the
      artifact digest (no re-publish).
- [ ] 4.2 Implement `label_publish.py`: create new normalized collections, link existing
      artifact versions, attach `LabelCard` metadata, set `production` alias on the new
      collection only.
- [ ] 4.3 **Test:** the old collection's artifact remains resolvable (not orphaned).
- [ ] 4.4 **Test:** the new collection carries the `production` alias and `LabelCard` metadata.
- [ ] 4.5 Implement idempotent re-run: skip collections already migrated (same pattern as
      `seed-registry`).
- [ ] 4.6 **Test:** re-running the migration skips already-migrated collections.

## 5. CLI

- [ ] 5.1 **Test:** `seed-label-registry` dry run prints planned collections without contacting
      wandb.
- [ ] 5.2 Implement `seed-label-registry` subcommand: dry-run by default, `--execute` to
      publish, `--only <collection>` for canary, `--verify` for read-back.
- [ ] 5.3 **Test:** `--only` filters to a single collection; unknown `--only` fails fast.
- [ ] 5.4 **Test:** `--verify` reads back the production alias from the live registry.
- [ ] 5.5 **Test:** credential guard (same as model `seed-registry`).

## 6. Verification and docs

- [ ] 6.1 Canary: migrate one collection with `--only`, verify consumer can read it.
- [ ] 6.2 Full migration: run `--execute` for the remaining collections.
- [ ] 6.3 Run `--verify` against the live registry.
- [ ] 6.4 Worked example: join one model to its training labels via the registries.
- [ ] 6.5 Update `docs/CHANGELOG.md` under `[Unreleased]`.
- [ ] 6.6 Update `docs/roadmap.md` to reflect #11 completion.
