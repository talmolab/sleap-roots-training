## 0. Gate

- [x] 0.1 Confirm `sleap-roots-contracts==0.1.0a6` is on PyPI and review the `a3 → a6` delta for
      changes to already-released contracts (design.md records the review — only `ModelCard`
      changed).
- [x] 0.2 Confirm every `mode` in the committed `model_selection.yaml` is in the contract's `Mode`
      vocabulary — if not, this is a migration, not an adoption, and stops here. (7 rows:
      `cylinder` ×6, `multiplant cylinder` ×1 — both in vocabulary.)
- [x] 0.3 Enumerate **every** consumer of `MODE_VOCAB`, not just the loader. Found two:
      `chooser.load_selection_matrix` (repo-owned matrix data) and `config._validate_experiment`
      (`config.py:200`, hand-written user config, added by Tier 1 / #20). Recorded in design.md.

## 1. Pin

- [x] 1.1 `uv add "sleap-roots-contracts==0.1.0a6"` (exact pin retained — design.md).
- [x] 1.2 Regenerate the lockfile; confirm `uv lock --check` passes.
- [x] 1.3 `uv run python -c "import sleap_roots_contracts as c; print(c.__version__)"` reports
      `0.1.0a6`, and `from sleap_roots_contracts import Mode` resolves to
      `('cylinder', 'multiplant cylinder', 'plate')`.

## 2. Collapse the mode vocabulary

- [x] 2.1 In `registry/chooser.py`, derive `MODE_VOCAB` from `sleap_roots_contracts.Mode` via
      `get_args`, keeping the `MODE_VOCAB` name and the loader's row-numbered error message.
- [x] 2.2 Update the module docstring/comment so the source of truth is stated where the constant
      lives, not only in the spec.
- [x] 2.3 Leave `SPECIES_VOCAB` local and say why in the same place.
- [x] 2.4 No change to `config.py` — it imports `MODE_VOCAB` and the vocabulary is set-identical,
      so `validate` behavior is unchanged. Decision recorded rather than code written.

## 3. Tests

Note: there is no RED step here — the bump changes no behavior in this repo (design.md). These are
regression guards on an invariant that previously held only because two lists agreed.

- [x] 3.1 `tests/test_registry_chooser.py`: assert `MODE_VOCAB` is the contract vocabulary
      **unforked**, plus a mirror asserting `SPECIES_VOCAB` stays local. Follows the existing
      `test_root_type_vocab_mirrors_cards_slots` drift-guard idiom.
      **Deviation from the proposal:** the originally-planned test ("every mode in the committed
      matrix is contract-valid") is *unwritable as a failing test* — the loader validates rows
      against `MODE_VOCAB`, which is now derived from `Mode`, so the assertion holds by
      construction and can never fail. That scenario's real enforcement is the loader raising at
      load time, already covered by `test_load_selection_matrix_has_seven_rows`. What is written
      instead guards the failure that *can* happen: a human re-forking the vocabulary locally
      (`frozenset(get_args(Mode)) | {"cyl"}`) to let a stray value through.
- [x] 3.2 `tests/test_registry_cards.py`: parametrized over every mode the loader accepts — a card's
      metadata validates against the real `ModelCard` and round-trips `mode` unchanged. Verified
      non-vacuous: the contract rejects `multiplant-cylinder`, `Cylinder`, `cyl`, and `" cylinder"`,
      so a slug leaking out of `card_to_metadata` fails this test.
- [x] 3.3 `tests/test_config.py`: lock exact matching of `experiment.mode` (`Cylinder`, `CYLINDER`,
      leading/trailing space, `multiplant-cylinder` all rejected), so a later normalization has to
      argue with a test first. Sits with the existing vocab-drift guards.
- [x] 3.4 Confirm the existing off-vocabulary rejection test (`mode: teacup`) still fails at the
      loader with the row-numbered error, not at `ModelCard`.
- [x] 3.5 Confirm `tests/test_registry_lineage.py` still passes — it asserts the recorded contract
      version against `importlib.metadata`, so it follows the pin with no edit.

## 4. Spec + docs

- [x] 4.1 Author the `model-registry` delta (2 requirements MODIFIED). **Not applied to
      `openspec/specs/` here** — per the OpenSpec workflow, `specs/` is updated by
      `openspec archive` in the follow-up archive PR, matching this repo's `#18`/`#19` precedent.
- [x] 4.2 `docs/CHANGELOG.md` Unreleased: the pin bump, the vocabulary collapse, the `config.py`
      surface, and the exact-matching decision.
- [x] 4.3 `openspec validate update-contracts-pin-0-1-0a6 --strict` passes.

## 5. Verify

- [x] 5.1 Run CI locally: `black --check`, `ruff check`, full `pytest`.
- [ ] 5.2 Open the PR; note that it unblocks #10 (`add-label-registry`).

## 6. Deferred (not this change)

- [ ] 6.1 Normalizing a hand-typed `experiment.mode` (lowercase + collapse whitespace, canonical
      value written back) is a `validate`-CLI behavior change belonging to the config capability,
      whose spec is still unarchived in `add-config-schema`. Decided against for now — see the
      exact-matching decision in design.md.
