# Tasks

## 0. Decisions required before implementation (blocking)

- [ ] 0.1 Approve the bundled-selector shape (`Selector`, `ModelCard.selectors`, scalar `root_type`).
- [ ] 0.2 Decide the **collection-id scheme** (`design.md` "Open question"). Recommendation: derive
      from `source_model_id`. This renames all 13 live production collections.
- [ ] 0.3 Decide the **migration strategy**: flag day vs tolerant read. Recommendation: tolerant
      read, so the production registry is never unreadable by an upgraded consumer.
- [ ] 0.4 Decide what happens to the 5 collections orphaned by the collapse (retire vs leave, and
      who owns the `production` alias on them).
- [ ] 0.5 Confirm cross-repo ownership and sequencing with the `sleap-roots-contracts` owner.

## 1. Contracts (`sleap-roots-contracts`, separate repo — must land first)

- [ ] 1.1 Add `Selector` (`species`, `mode: Mode`, `age_min`, `age_max`) with the existing
      `age_min`/`age_max` validation (reject `bool`/`numpy.bool_`, enforce ordering).
- [ ] 1.2 Change `ModelCard` to `root_type` + `selectors: tuple[Selector, ...]`; reject an empty
      `selectors`.
- [ ] 1.3 If tolerant read is chosen, accept a legacy flat card and lift it to a single selector.
- [ ] 1.4 Release a new pre-release version.

## 2. Consumer (`sleap-roots-predict`, separate repo)

- [ ] 2.1 Generalize `choose_models` to "any selector matches all of species/mode/age".
- [ ] 2.2 Match age against the **matching selector**, never a card-level min/max (see `design.md`
      risks — otherwise canola silently gains a year of coverage).
- [ ] 2.3 Add a regression test that a card serving (canola, cylinder, 2–13) and (arabidopsis,
      multiplant cylinder, 2–14) does **not** match (canola, multiplant cylinder) or (canola, age 14).
- [ ] 2.4 Pin the new contracts version.

## 3. This repo — expansion and metadata

- [ ] 3.1 Bump the `sleap-roots-contracts` pin.
- [ ] 3.2 Rewrite `expand_rows_to_cards` to group by `(source_model_id, root_type)` and attach one
      selector per contributing row, de-duplicated and deterministically ordered.
- [ ] 3.3 Update `card_to_metadata` to emit `selectors` + `root_type` + `source_model_id`, still
      omitting `registry_id` / `version` / `weights_checksum`.
- [ ] 3.4 Implement the chosen `collection_id` scheme; keep the duplicate-id fail-fast guard.
- [ ] 3.5 Assert every physical model resolves to exactly one `root_type`, failing the seed loudly if
      a future matrix edit breaks that assumption (the whole design rests on it).

## 4. This repo — publishing

- [ ] 4.1 Publish one artifact per physical model; delete the per-species duplicate-publish path.
- [ ] 4.2 Verify a re-seed of unchanged weights produces an **unchanged** `weights_checksum`
      (Bloom idempotency). Verify, do not assume.

## 5. Tests

- [ ] 5.1 Expansion yields **exactly 8 cards** from the committed matrix, with the shared primary
      model carrying 4 selectors and the two lateral models carrying 2 each.
- [ ] 5.2 Every card's metadata validates against the real `ModelCard`.
- [ ] 5.3 Cross-product regression: no card matches a (species, mode) pair absent from its selectors.
- [ ] 5.4 Update `tests/test_registry_cards.py`, `test_registry_chooser.py`, `test_registry_smoke.py`.
- [ ] 5.5 Full suite, `black --check`, `ruff check` green.

## 6. Migration and docs

- [ ] 6.1 Re-seed the 8 collections against the live registry (requires a wandb credential; do not
      run against production while exploring).
- [ ] 6.2 Execute the 0.4 decision for the orphaned collections.
- [ ] 6.3 Update `docs/` and `CHANGELOG.md`; note the breaking contract change and the registry-id
      rename.
- [ ] 6.4 Comment the outcome on #39; link sleap-roots-predict#14 and #46 so they do not drift.
