## Why

This repo pins `sleap-roots-contracts==0.1.0a3`. Three releases have shipped since, and `0.1.0a6`
is now on PyPI. Two things follow from that.

**The mode vocabulary is duplicated, and `0.1.0a6` ends the duplication.** `chooser.MODE_VOCAB` is a
hand-maintained `frozenset({"cylinder", "multiplant cylinder", "plate"})` whose only job is to keep
this producer's values matchable by the `sleap-roots-predict` consumer. `0.1.0a6` promotes exactly
that vocabulary into the contract as `Mode`, and makes `ModelCard.mode` a `Mode` rather than a free
`str` — so the contract now rejects at construction what our loader could previously only be
*trusted* to have rejected earlier. Two copies of a vocabulary whose whole purpose is
producer/consumer agreement is the one thing that vocabulary must not be.

**`0.1.0a6` on PyPI is the stated blocker for `add-label-registry` (#10).** That change needs
`LabelCard`, which does not exist in `0.1.0a3`. Bumping the pin here is the unblock.

The bump is safe to take now: the contract's `Mode` is set-identical to our `MODE_VOCAB`, and all
7 rows of the committed `model_selection.yaml` use only `cylinder` / `multiplant cylinder`. No card
that validates today stops validating. See design.md for the a3→a6 delta review.

## What Changes

- **Bump the runtime pin** `sleap-roots-contracts==0.1.0a3` → `==0.1.0a6` (exact pin retained — see
  design.md) and regenerate `uv.lock`.
- **Collapse `chooser.MODE_VOCAB` into the contract-owned `Mode`.** The name and the loader's
  error message are kept; only the source of the values moves. `SPECIES_VOCAB` stays local — the
  contract models no species vocabulary.
- **Guard the producer/consumer agreement with tests**, so a future contract change that narrows
  `Mode`, or a matrix row that drifts off-vocabulary, fails here rather than silently producing
  cards the consumer can never match.
- **Lock exact mode matching as a stated decision** (no case or whitespace normalization) at every
  surface — hand-written `experiment.mode`, published card metadata, consumer selection. Already
  the behavior; promoted to a decision because the contract now owns the vocabulary. See design.md.
- Spec: restate the mode-vocabulary requirement in terms of the contract instead of re-listing the
  values in prose.

**Not a breaking change for this repo.** `ModelCard.mode` tightening is **BREAKING (validation)**
upstream, but no input this repo produces or accepts changes behavior. This is an adoption, not a
migration.

## What This Change Does *Not* Do

- **Adopt `LabelCard`.** That is `add-label-registry` (#10), which this change unblocks.
- **Touch `resolve_params` or `PredictionManifest`** (added in `0.1.0a4` / `0.1.0a5`). Neither is
  imported here; both are consumer-side surface for `sleap-roots-predict` / `bloomctl`.
- **Change the committed selection matrix.** No row needs migrating.

## Impact

- **Affected specs:** `model-registry` (3 requirements MODIFIED). The two vocabulary requirements
  change no behavior — they restate where the `mode` values come from. The third, **Registry Seeding
  CLI with Confirmed Execution**, does: a rejected selection matrix now reaches the operator as a
  clean CLI error rather than an unhandled traceback.
- **Affected code:**
  - Pin + lock: `pyproject.toml`, `uv.lock`
  - Source: `src/sleap_roots_training/registry/chooser.py`, `src/sleap_roots_training/config.py`,
    `src/sleap_roots_training/cli.py`
  - Tests: `tests/test_registry_chooser.py`, `tests/test_registry_cards.py`,
    `tests/test_config.py`, `tests/test_registry_cli.py`, `tests/test_training_docs.py`
  - Docs + change record: `docs/CHANGELOG.md`, and this change's `proposal.md` / `design.md` /
    `tasks.md` / `specs/model-registry/spec.md`
- **Note:** `config.py` consumes `MODE_VOCAB` to validate the hand-written `experiment.mode`
  (`config.py:_validate_experiment`), so the contract now governs a user-facing config field and not
  only published metadata. The *vocabulary* there is set-identical, so no config that validated
  before stops validating — but the file is **not** unchanged, contrary to an earlier draft of this
  section. There are **two** user-visible behavior changes, both arriving from review rounds rather
  than from the bump:
  1. `_check_vocab` gained a "did you mean" hint (and an `ascii()` rendering for homoglyphs). Because
     that helper is shared, this changed the error text for `experiment.species` and
     `experiment.root_type` as well as `experiment.mode` — wider than this change's subject; see the
     scope note in `design.md` and `tasks.md` §2.5.
  2. `seed-registry` now packages a selection-matrix rejection as a CLI error rather than letting it
     surface as a traceback (`tasks.md` §2.6). This is the third MODIFIED requirement above.

  Neither changes what is *accepted* or *published* — only what is printed when something is
  rejected. The new contract coupling itself is recorded in `design.md`.
- **Affected issues:** unblocks #10 (`add-label-registry`); closes the `cylinder`/`cyl` vocabulary
  split noted in `sleap-roots-contracts` `0.1.0a6`.
