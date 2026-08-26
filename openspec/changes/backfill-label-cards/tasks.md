## 0. Pre-implementation decisions (gate: all resolved before §1)

- [x] 0.1 ~~Verify `LabelCard` schema permits `null` for provenance fields~~ — **resolved:** the
      seven provenance fields are `Optional`; the other 15 are required and non-nullable.
      Confirmed against the pinned `0.1.0a6`. See D1 (the seven) and D7 (the four required ones
      that are not recoverable from the blob). The earlier "no contracts bump needed" reading
      answered only the provenance half of this question.
- [x] 0.2 ~~Decide disposition of medicago~~ — **resolved:** `medicago` is in scope.
- [x] 0.3 ~~Confirm `wheat`, `sorghum`, `medicago` should be added to `SPECIES_VOCAB`~~ —
      **resolved: no.** They go into a new label-side `LABEL_SPECIES_VOCAB`; `SPECIES_VOCAB` is
      unchanged, because it validates the model selection matrix and `experiment.species` in a
      training config, not just labels. See D5.
- [x] 0.4 ~~Verify the contract's `RootType` accepts `seminal`~~ — **resolved: it does not**, on
      the pin or at contracts HEAD (`0.1.0a8`). Handled by a new `LabelRootType` upstream rather
      than by widening `RootType`. See D3.

## 1. Upstream: contracts `0.1.0a9`

Blocks §3. Tasks 1.4–1.5 are conditional on §2's findings, so this section completes *after* §2
even though it starts before it.

- [ ] 1.1 Open a change directory in `sleap-roots-contracts` for the release, following the
      `archive/2026-08-05-update-contracts-pin-0-1-0a6` precedent (proposal + design + `a6 → a9`
      delta review). The pin here also has to absorb `a7` and `a8`, which this repo skipped.
- [ ] 1.2 **Test (contracts):** `LabelCard(root_type="seminal", ...)` validates; `ModelCard`
      still rejects it (red — `RootType` has no `seminal`).
- [ ] 1.3 Add `LabelRootType = Literal["primary", "lateral", "crown", "seminal"]` to
      `models.py`; re-annotate `LabelCard.root_type` to it. Leave `RootType` and
      `ModelCard.root_type` untouched (green).
- [ ] 1.4 **Conditional on 2.5** — if any of `age_min`/`age_max`/`n_plants`/`n_scans` is
      unrecoverable for any collection, relax that field to `Optional` in the same release, with
      the reason recorded in the contracts change's design.
- [ ] 1.5 Cut `0.1.0a9`; bump the pin in `pyproject.toml` here and confirm the full suite passes
      against it.

## 2. Provenance reconstruction (archaeology) — gates §3

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
      This is also the verification `skeletons.yaml`'s header names as what flips its remaining
      rows from `verified: false` — record the result in a form that change can consume.
- [ ] 2.5 **D7 gate.** Report, per collection, whether `age_min`, `age_max`, `n_plants`, and
      `n_scans` were recovered. Expect the two soybean (`Z:`-drive) collections to be the hard
      cases for age, and `n_plants`/`n_scans` to be unrecoverable from any blob. Whichever fields
      come back unrecoverable are what 1.4 relaxes; if all four are recovered everywhere, 1.4 is
      skipped and the release carries only `LabelRootType`.

## 3. Vocabulary split

Depends on §1 landing (`LABEL_ROOT_TYPE_VOCAB` derives from the new contract symbol).

- [ ] 3.1 **Test:** `LABEL_ROOT_TYPE_VOCAB` is derived from the contract's `LabelRootType`, is a
      strict superset of `ROOT_TYPE_VOCAB`, and the difference is exactly `{"seminal"}` (red).
- [ ] 3.2 Add `LABEL_ROOT_TYPE_VOCAB` to `registry/chooser.py`, derived via `get_args` and
      carrying the same import guard `MODE_VOCAB` and `ROOT_TYPE_VOCAB` use — including fault
      injection over the same six reshapes (green).
- [ ] 3.3 **Test:** `LABEL_SPECIES_VOCAB` is a strict superset of `SPECIES_VOCAB` and the
      difference is exactly `{"wheat", "sorghum", "medicago"}` (red).
- [ ] 3.4 Add `LABEL_SPECIES_VOCAB` to `registry/chooser.py`, defined as `SPECIES_VOCAB | {...}`
      so the superset relation cannot drift (green). Document that the label-side vocabularies
      are supersets of the model-side ones and why.
- [ ] 3.5 **Test:** `PackageMetadata` accepts `species="wheat"` and `root_types=("seminal",)`,
      and the skeleton-table loader accepts a `wheat` / `seminal` row (red).
- [ ] 3.6 Point `labeling/metadata.py` and `labeling/skeletons.py` at the label-side vocabularies
      (green).
- [ ] 3.7 **Test — the half that must NOT change:** `experiment.species: wheat` and
      `experiment.root_type: seminal` are still rejected by `config.validate`; the selection-matrix
      loader still rejects a `wheat` row; `frozenset(cards._ROOT_SLOTS) == chooser.ROOT_TYPE_VOCAB`
      still holds. This is the test that makes the split a split rather than a widening.
- [ ] 3.8 Confirm all existing tests still pass after the vocabulary split (`pytest`).

## 4. LabelCard metadata construction

- [ ] 4.1 **Test:** for each of the 8 collections, a `LabelCard` can be constructed from the
      reconstructed metadata (null where unrecoverable *and* the field is `Optional`) and
      validates against the contract.
- [ ] 4.2 Implement `label_cards.py`: a mapping from each old collection name to its
      `LabelCard` fields (species, mode, root_type, node_count, age range, provenance fields).
      Unrecoverable `Optional` fields are explicitly `None`.
- [ ] 4.3 **Test:** the normalized collection name for each card follows the
      `{species}-{mode}-{root_type}` convention.
- [ ] 4.4 Implement `collection_id()` for label cards following D4's naming convention.
- [ ] 4.5 **Test:** no two cards produce the same collection id (uniqueness guard).
- [ ] 4.6 **Test:** every card's `mode` validates against `MODE_VOCAB`, every card's `species`
      against `LABEL_SPECIES_VOCAB`, and every card's `root_type` against
      `LABEL_ROOT_TYPE_VOCAB`.
- [ ] 4.7 **Test:** no card carries a fabricated value for a field §2 reported as unrecovered —
      it is either `None` or the card is not constructible, never a placeholder.

## 5. Registry migration (publish + link)

- [ ] 5.1 **Test:** linking an existing artifact version into a new collection preserves the
      artifact digest (no re-publish).
- [ ] 5.2 Implement `label_publish.py`: create new normalized collections, link existing
      artifact versions, attach `LabelCard` metadata, set `production` alias on the new
      collection only.
- [ ] 5.3 **Test:** the old collection's artifact remains resolvable (not orphaned).
- [ ] 5.4 **Test:** the new collection carries the `production` alias and `LabelCard` metadata.
- [ ] 5.5 Implement idempotent re-run: skip collections already migrated (same pattern as
      `seed-registry`).
- [ ] 5.6 **Test:** re-running the migration skips already-migrated collections.

## 6. CLI

- [ ] 6.1 **Test:** `seed-label-registry` dry run prints planned collections without contacting
      wandb.
- [ ] 6.2 Implement `seed-label-registry` subcommand: dry-run by default, `--execute` to
      publish, `--only <collection>` for canary, `--verify` for read-back, `--force` to re-link.
- [ ] 6.3 **Test:** `--only` filters to a single collection; unknown `--only` fails fast.
- [ ] 6.4 **Test:** `--verify` reads back the production alias from the live registry.
- [ ] 6.5 **Test:** credential guard (same as model `seed-registry`).

## 7. Verification and docs

- [ ] 7.1 Dry-run review: print all eight planned collections and check each against §2's
      recorded findings by hand. This is the gate for a name that cannot be un-created.
- [ ] 7.2 Canary: migrate `arabidopsis-cylinder-primary` with `--only`, verify consumer can read
      it. Chosen because it depends on neither D3 nor D7 (see D6).
- [ ] 7.3 Full migration: run `--execute` for the remaining seven collections.
- [ ] 7.4 Run `--verify` against the live registry.
- [ ] 7.5 Worked example: join one model to its training labels via the registries.
- [ ] 7.6 Update `docs/CHANGELOG.md` under `[Unreleased]`.
- [ ] 7.7 Update `docs/roadmap.md` to reflect #11 completion.
