import json
import os
import subprocess
import sys

import pytest
from sleap_roots_contracts import ModelCard, Selector

from sleap_roots_training.registry import cards, chooser
from sleap_roots_training.registry.chooser import SelectionRow

CPA_PRIMARY = "canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743"
CANOLA_LATERAL = "canola/lateral/240611_083419.multi_instance.n=631"
ARABIDOPSIS_LATERAL = "arabidopsis/lateral/240130_140452.multi_instance.n=337"


def _row(species, mode, age, primary=None, lateral=None, crown=None):
    return SelectionRow(species, mode, age, primary, lateral, crown)


def _sel(card):
    """The card's selectors as plain comparable 4-tuples."""
    return [(s.species, s.mode, s.age_min, s.age_max) for s in card.selectors]


def _by_model(all_cards):
    return {c.source_model_id: c for c in all_cards}


# --- Expansion shapes (one card per physical model) ---


def test_primary_and_lateral_row_two_cards():
    row = _row("soybean", "cylinder", "2, 3", primary="s/p", lateral="s/l")
    result = cards.expand_rows_to_cards([row])
    assert {c.root_type for c in result} == {"primary", "lateral"}
    assert len(result) == 2


def test_primary_and_crown_no_lateral():
    row = _row("rice", "cylinder", "2, 3, 4, 5", primary="r/p", crown="r/c")
    result = cards.expand_rows_to_cards([row])
    assert sorted(c.root_type for c in result) == ["crown", "primary"]


def test_crown_only_row_single_card():
    # Re-keyed for 3.2/3.3: the age window moved off the card and onto the selector,
    # so reading `result[0].age_min` no longer type-checks. The invariant is the same.
    row = _row("rice", "cylinder", "6, 7, 8, 9, 10", crown="r/older/c")
    result = cards.expand_rows_to_cards([row])
    assert len(result) == 1
    assert result[0].root_type == "crown"
    assert _sel(result[0]) == [("rice", "cylinder", 6, 10)]


def test_primary_only_row_one_card():
    row = _row("soybean", "cylinder", "2, 3", primary="s/p")  # lateral+crown null
    result = cards.expand_rows_to_cards([row])
    assert len(result) == 1 and result[0].root_type == "primary"


def test_all_null_slots_produce_no_card():
    row = _row("soybean", "cylinder", "2, 3")  # all three model ids null
    assert cards.expand_rows_to_cards([row]) == []


# --- 3.8: the real matrix collapses to exactly 8 cards ---


def test_real_matrix_yields_eight_cards():
    all_cards = cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    assert len(all_cards) == 8, "7 committed rows over 8 physical models -> 8 cards"
    # One card per physical model is the whole design; assert it directly.
    assert len({c.source_model_id for c in all_cards}) == 8


def test_shared_primary_is_one_card_with_four_selectors():
    all_cards = cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    shared = [c for c in all_cards if c.source_model_id == CPA_PRIMARY]
    assert len(shared) == 1, "the generalist primary is ONE card, not four"
    assert shared[0].root_type == "primary"
    assert len(shared[0].selectors) == 4


def test_shared_laterals_carry_two_selectors_each():
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    assert len(by_model[CANOLA_LATERAL].selectors) == 2
    assert len(by_model[ARABIDOPSIS_LATERAL].selectors) == 2


def test_legacy_models_carry_no_sleap_nn_version():
    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        meta = cards.card_to_metadata(card)
        assert "sleap_nn_version" not in meta
        model_card = ModelCard.model_validate(
            {
                **meta,
                "registry_id": "rid",
                "version": "v0",
                "weights_checksum": "0" * 64,
            }
        )
        assert model_card.sleap_nn_version is None


# --- 3.10 / 3.19: the exact selector sets, and the exact order ---

#: Set equality, so no window may be widened or dropped (3.10). The shared primary's
#: canola window is 2-13 while the other three are 2-14 -- the single most important
#: fact this design preserves, and the one a card-level age bound would destroy.
EXPECTED_SELECTORS_BY_MODEL = {
    "soybean/primary/221003_111420.multi_instance.n=1389": {
        ("soybean", "cylinder", 2, 8),
    },
    "soybean/lateral/lateral_root_221006_172103.multi_instance.n=482": {
        ("soybean", "cylinder", 2, 8),
    },
    CPA_PRIMARY: {
        ("canola", "cylinder", 2, 13),
        ("pennycress", "cylinder", 2, 14),
        ("arabidopsis", "multiplant cylinder", 2, 14),
        ("arabidopsis", "cylinder", 2, 14),
    },
    CANOLA_LATERAL: {
        ("canola", "cylinder", 2, 13),
        ("pennycress", "cylinder", 2, 14),
    },
    ARABIDOPSIS_LATERAL: {
        ("arabidopsis", "multiplant cylinder", 2, 14),
        ("arabidopsis", "cylinder", 2, 14),
    },
    "rice/younger/primary/230104_182346.multi_instance.n=720": {
        ("rice", "cylinder", 2, 5),
    },
    "rice/younger/crown/220821_163331.multi_instance.n=867": {
        ("rice", "cylinder", 2, 5),
    },
    "rice/older/crown/221208_113552.multi_instance.n=574": {
        ("rice", "cylinder", 6, 10),
    },
}


def test_every_card_carries_exactly_its_expected_selectors():
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    assert set(by_model) == set(EXPECTED_SELECTORS_BY_MODEL)
    for model_id, expected in EXPECTED_SELECTORS_BY_MODEL.items():
        assert set(_sel(by_model[model_id])) == expected, model_id


def test_shared_primary_selectors_are_in_the_exact_expected_order():
    # 3.10's set equality plus 3.12/3.13's "same order twice" are all satisfied by a
    # stably-WRONG order. Only an ordered literal pins the absolute one.
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    assert _sel(by_model[CPA_PRIMARY]) == [
        ("arabidopsis", "cylinder", 2, 14),
        ("arabidopsis", "multiplant cylinder", 2, 14),
        ("canola", "cylinder", 2, 13),
        ("pennycress", "cylinder", 2, 14),
    ]


def test_the_two_rice_crown_models_stay_two_distinct_cards():
    # 3.25: same species, same mode, same root type, different age windows and
    # different weights. Collapsing these would be the design's worst failure.
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    younger = by_model["rice/younger/crown/220821_163331.multi_instance.n=867"]
    older = by_model["rice/older/crown/221208_113552.multi_instance.n=574"]
    assert cards.collection_id(younger) != cards.collection_id(older)
    assert _sel(younger) == [("rice", "cylinder", 2, 5)]
    assert _sel(older) == [("rice", "cylinder", 6, 10)]


# --- 3.29: the dedup rule the committed matrix cannot exercise ---


def test_identical_rows_contribute_one_selector():
    # No two committed rows contribute an identical selector to one card, so 3.10 and
    # 3.19 both stay green if the dedupe is deleted. A synthetic duplicate is the only
    # thing that tests it. The matrix loader does not reject duplicate rows.
    rows = [
        _row("soybean", "cylinder", "2, 3", primary="s/p"),
        _row("soybean", "cylinder", "2, 3", primary="s/p"),
    ]
    result = cards.expand_rows_to_cards(rows)
    assert len(result) == 1
    assert len(result[0].selectors) == 1
    assert _sel(result[0]) == [("soybean", "cylinder", 2, 3)]


# --- 3.11 / 3.5 / 3.5b: the fail-fast guards ---


def test_a_model_in_two_root_slots_fails_fast():
    # The whole design rests on root_type being intrinsic to the weights.
    rows = [_row("soybean", "cylinder", "2, 3", primary="s/shared", lateral="s/shared")]
    with pytest.raises(ValueError) as excinfo:
        cards.expand_rows_to_cards(rows)
    message = str(excinfo.value)
    assert "s/shared" in message
    assert "primary" in message and "lateral" in message


def test_two_models_sharing_a_selector_fail_fast():
    # 3.5b. Today this is caught incidentally, because the collection id is built from
    # the selection tuple and the duplicate-id check rejects the pair. An id derived
    # from the model gives them DISTINCT ids, so both would publish, both would take
    # the production alias, and the consumer would find two matching production cards.
    rows = [
        _row("soybean", "cylinder", "2, 3", primary="s/one"),
        _row("soybean", "cylinder", "2, 3", primary="s/two"),
    ]
    with pytest.raises(ValueError) as excinfo:
        cards.expand_rows_to_cards(rows)
    message = str(excinfo.value)
    assert "s/one" in message and "s/two" in message
    assert "soybean" in message and "cylinder" in message


def test_the_collision_guard_discriminates():
    # The negative control: two models of one root type whose selectors merely overlap
    # in species but differ in age must NOT trip the guard.
    rows = [
        _row("soybean", "cylinder", "2, 3", primary="s/one"),
        _row("soybean", "cylinder", "4, 5", primary="s/two"),
    ]
    result = cards.expand_rows_to_cards(rows)
    assert len(result) == 2


def test_different_root_types_may_share_a_selector():
    # A primary and a lateral model legitimately serve the same (species, mode, age).
    rows = [_row("soybean", "cylinder", "2, 3", primary="s/p", lateral="s/l")]
    result = cards.expand_rows_to_cards(rows)
    assert len(result) == 2


# --- 3.13: order is independent of matrix row order ---


def test_expansion_is_independent_of_row_order():
    rows = list(chooser.load_selection_matrix().rows)
    forward = cards.expand_rows_to_cards(rows)
    reverse = cards.expand_rows_to_cards(list(reversed(rows)))
    assert [cards.card_to_metadata(c) for c in forward] == [
        cards.card_to_metadata(c) for c in reverse
    ]


# --- 3.12: order is stable across processes with differing PYTHONHASHSEED ---

_DUMP_SELECTORS = """
import json
from sleap_roots_training.registry import cards, chooser
rows = chooser.load_selection_matrix().rows
print(json.dumps([cards.card_to_metadata(c) for c in cards.expand_rows_to_cards(rows)]))
"""


def _expansion_under_hashseed(seed):
    # `env = dict(os.environ)` then mutate -- a bare env={"PYTHONHASHSEED": seed}
    # breaks on Windows for want of SYSTEMROOT. A same-process re-expansion would be
    # vacuous, and PYTHONHASHSEED=0 *disables* randomization, so 0-vs-nonzero is the
    # discriminating pair. Comparing the serialized JSON also discharges the spec's
    # "byte-identical metadata" clause.
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    result = subprocess.run(
        [sys.executable, "-B", "-c", _DUMP_SELECTORS],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("seed", ["1", "2", "12345"])
def test_selector_order_is_stable_across_hash_seeds(seed):
    assert _expansion_under_hashseed(seed) == _expansion_under_hashseed("0")


# --- 3.3 / 3.23 / 3.23b / 3.22: the emitted metadata ---


def test_card_to_metadata_exact_card_level_keys():
    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        meta = cards.card_to_metadata(card)
        assert set(meta) == {"root_type", "selectors", "source_model_id"}
        # Intrinsics MUST NOT be present (the consumer injects them).
        assert not ({"registry_id", "version", "weights_checksum"} & set(meta))
        # No card-level selection dimensions survive the reshape.
        assert not ({"species", "mode", "age_min", "age_max"} & set(meta))


def test_each_selector_dict_has_the_exact_key_set():
    # 3.23b. `Selector` is extra="ignore", so a stray or typo'd key inside a selector
    # dict is silently DROPPED by ModelCard validation rather than rejected -- the
    # contract cannot catch it for us. Asserted on every selector of every card, not a
    # sample. A *missing* key still fails loudly on the contract side.
    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        for selector in cards.card_to_metadata(card)["selectors"]:
            assert set(selector) == {"species", "mode", "age_min", "age_max"}


def test_selectors_are_json_native_dicts_not_pydantic_models():
    # `wandb.Artifact(metadata=...)` runs the mapping through validate_metadata, which
    # COERCES rather than rejects: a pydantic model degrades to its repr string and a
    # NamedTuple to a positional list, publishing unreadable metadata with a zero exit.
    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        meta = cards.card_to_metadata(card)
        assert isinstance(meta["selectors"], list)
        for selector in meta["selectors"]:
            assert type(selector) is dict, type(selector)
            assert isinstance(selector["species"], str)
            assert isinstance(selector["mode"], str)
            assert type(selector["age_min"]) is int
            assert type(selector["age_max"]) is int


def test_sleap_nn_version_stays_card_level_and_is_absent_from_selector():
    # 3.22: it describes the weights, not a selection context.
    assert "sleap_nn_version" not in Selector.model_fields
    assert "sleap_nn_version" in ModelCard.model_fields
    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        for selector in cards.card_to_metadata(card)["selectors"]:
            assert "sleap_nn_version" not in selector


def test_mode_is_stored_raw_not_slugged():
    # The silent-break guard: if card_to_metadata ever emitted the hyphenated
    # collection-id slug, the loader would still pass and the consumer would silently
    # never match.
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    modes = {
        s["mode"] for s in cards.card_to_metadata(by_model[CPA_PRIMARY])["selectors"]
    }
    assert "multiplant cylinder" in modes
    assert "multiplant-cylinder" not in modes


# --- root slots: membership is the contract's, order is ours ---------------------------

#: The slot order spelled out, for the same reason `_EXPECTED_MODES` below is. This is the
#: independent witness for the *ordering* half of the split: `_ROOT_SLOTS` is no longer
#: derived from anything, so what needs pinning is that a future "just use `get_args`"
#: edit cannot slip through unnoticed.
_EXPECTED_ROOT_SLOTS = ("primary", "lateral", "crown")


def test_root_slot_membership_is_the_contract_vocabulary():
    # Membership has one owner -- `sleap_roots_contracts.RootType`, via
    # `chooser.ROOT_TYPE_VOCAB`. Adding a fourth root type upstream without adding a slot
    # here means every card for it is silently never emitted, which is exactly the drift
    # that made three hand-maintained copies of this vocabulary a problem.
    assert frozenset(cards._ROOT_SLOTS) == chooser.ROOT_TYPE_VOCAB
    assert len(cards._ROOT_SLOTS) == len(chooser.ROOT_TYPE_VOCAB)  # no duplicate slot


def test_root_slot_order_is_owned_here_not_by_the_contract():
    """The deliberate half of the split: ordering is a presentation decision, not a contract.

    ``_ROOT_SLOTS`` is *not* ``get_args(RootType)``. Reordering a ``Literal``'s members is
    a no-op for a type annotation, so upstream is free to do it in a patch release -- and
    if slot order were derived from it, that no-op would quietly reorder every card
    ``expand_rows_to_cards`` emits, and with it the ``seed-registry`` plan an operator
    reads before confirming a publish. Card order is this repo's to choose, so it is
    pinned here rather than inherited.
    """
    assert cards._ROOT_SLOTS == _EXPECTED_ROOT_SLOTS


def test_cards_are_emitted_in_row_then_root_slot_order():
    # The assertion above only pins the constant; this pins what the constant is *for*.
    # Nothing else in the suite constrains cross-root emission order -- the shape tests
    # use a set, `sorted()`, and `Counter` -- so without this, `expand_rows_to_cards`
    # could stop honoring `_ROOT_SLOTS` (say, by iterating the `model_ids` dict built
    # from a reordered source) and the order pinned above would mean nothing.
    #
    # Two rows, not one, because the documented contract is "row-then-root-slot order"
    # (see `expand_rows_to_cards`) and a one-row fixture pins only half of it: transpose
    # the loop nesting -- slots outermost, rows innermost, emitting every primary card
    # before any lateral -- and a single-row assertion still passes unchanged.
    rows = [
        _row("rice", "cylinder", "2, 3", primary="r/p", lateral="r/l", crown="r/c"),
        _row("soybean", "cylinder", "2, 3", primary="s/p", lateral="s/l", crown="s/c"),
    ]
    result = cards.expand_rows_to_cards(rows)
    assert [(c.species, c.root_type) for c in result] == [
        ("rice", "primary"),
        ("rice", "lateral"),
        ("rice", "crown"),
        ("soybean", "primary"),
        ("soybean", "lateral"),
        ("soybean", "crown"),
    ]


# --- 3.20: every accepted mode still round-trips through the real ModelCard ---

#: The vocabulary spelled out, NOT `sorted(chooser.MODE_VOCAB)`. Parametrizing over the
#: live set means an upstream *narrowing* silently shrinks the suite instead of failing
#: it: drop `"plate"` upstream and the `[plate]` case simply stops existing -- the suite
#: total drops by one and nothing is red. Spelled out, a narrowing is a failure.
_EXPECTED_MODES = ["cylinder", "multiplant cylinder", "plate"]


def test_expected_modes_match_the_live_vocabulary():
    assert set(_EXPECTED_MODES) == chooser.MODE_VOCAB
    assert len(_EXPECTED_MODES) == len(chooser.MODE_VOCAB)


@pytest.mark.parametrize("mode", _EXPECTED_MODES)
def test_every_accepted_mode_round_trips_through_the_real_modelcard(mode):
    card = cards.Card(
        root_type="primary",
        selectors=(Selector(species="rice", mode=mode, age_min=2, age_max=14),),
        source_model_id="r/p",
    )
    meta = cards.card_to_metadata(card)
    model_card = ModelCard.model_validate(
        {**meta, "registry_id": "rid", "version": "v1", "weights_checksum": "sha"}
    )
    assert model_card.selectors[0].mode == mode  # raw value, unslugged and uncased


def test_every_committed_matrix_card_validates_against_the_real_modelcard():
    # Nothing in `src/` ever constructs a `ModelCard` -- `publish.py` writes
    # `card_to_metadata` straight into `wandb.Artifact` -- so the contract's validation
    # is *only* ever exercised by tests on this side of the wire. The consumer is where
    # a bad card would otherwise first be noticed, which is too late.
    matrix = chooser.load_selection_matrix()
    all_cards = cards.expand_rows_to_cards(matrix.rows)
    assert len(all_cards) == 8

    for card in all_cards:
        meta = cards.card_to_metadata(card)
        model_card = ModelCard.model_validate(
            {
                **meta,
                "registry_id": cards.collection_id(card),
                "version": "v0",
                "weights_checksum": "0" * 64,
            }
        )
        assert model_card.root_type == card.root_type
        assert [
            (s.species, s.mode, s.age_min, s.age_max) for s in model_card.selectors
        ] == _sel(card)


# --- 3.21: an empty selectors list is rejected by the contract ---


def test_empty_selectors_metadata_fails_modelcard_validation():
    import pydantic

    with pytest.raises(pydantic.ValidationError) as excinfo:
        ModelCard.model_validate(
            {
                "root_type": "primary",
                "selectors": [],
                "source_model_id": "s/p",
                "registry_id": "rid",
                "version": "v0",
                "weights_checksum": "0" * 64,
            }
        )
    # Exactly one error, located at `selectors` -- the contract uses a BeforeValidator
    # rather than Field(min_length=1) precisely so a card whose only selector is
    # invalid does not also report a spurious `too_short`.
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("selectors",)


# --- 3.15: no card matches a (species, mode) pair absent from its selectors ---


def test_no_card_advertises_an_untrained_species_mode_pair():
    # The cross-product regression. Independently tupling species and mode would make
    # the shared primary match (canola, multiplant cylinder) -- never trained, never
    # validated. The any-selector rule must not.
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    pairs = {(s.species, s.mode) for s in by_model[CPA_PRIMARY].selectors}
    assert ("canola", "cylinder") in pairs
    assert ("arabidopsis", "multiplant cylinder") in pairs
    # The cross-product combinations that must NOT appear:
    assert ("canola", "multiplant cylinder") not in pairs
    assert ("pennycress", "multiplant cylinder") not in pairs


def test_canola_does_not_gain_a_year_from_the_shared_card():
    # Age must be read off the MATCHING selector, never a card-level bound. A card-level
    # max over this card's four selectors would be 14 and would silently extend canola's
    # validated window by a year.
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    canola = [s for s in by_model[CPA_PRIMARY].selectors if s.species == "canola"]
    assert len(canola) == 1
    assert (canola[0].age_min, canola[0].age_max) == (2, 13)


# --- 3.4 / 3.9 / 3.14 / 3.30: collection ids ---

EXPECTED_COLLECTION_BY_MODEL = {
    "soybean/primary/221003_111420.multi_instance.n=1389": "soybean-primary-221003_111420.multi_instance.n-1389",
    "soybean/lateral/lateral_root_221006_172103.multi_instance.n=482": "soybean-lateral-lateral_root_221006_172103.multi_instance.n-482",
    CPA_PRIMARY: "canola_pennycress_arabidopsis-primary-240611_102513.multi_instance.n-743",
    CANOLA_LATERAL: "canola-lateral-240611_083419.multi_instance.n-631",
    ARABIDOPSIS_LATERAL: "arabidopsis-lateral-240130_140452.multi_instance.n-337",
    "rice/younger/primary/230104_182346.multi_instance.n=720": "rice-younger-primary-230104_182346.multi_instance.n-720",
    "rice/younger/crown/220821_163331.multi_instance.n=867": "rice-younger-crown-220821_163331.multi_instance.n-867",
    "rice/older/crown/221208_113552.multi_instance.n=574": "rice-older-crown-221208_113552.multi_instance.n-574",
}


def test_collection_id_derives_from_the_source_model_id():
    # 3.30's anchor, re-keyed off the old "rice-cylinder-crown-age6-10" literal. The
    # formula is settled: replace each `/` and each `=` with `-`, change nothing else.
    by_model = _by_model(
        cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    )
    for model_id, expected in EXPECTED_COLLECTION_BY_MODEL.items():
        assert cards.collection_id(by_model[model_id]) == expected


def test_matrix_lock_model_to_selectors():
    # 3.9. The old lock asserted {collection_id: source_model_id}; under an
    # id-derived-from-model scheme that degenerates to {slug(x): x} and stops testing
    # anything. Lock the real matrix invariant instead: model -> its selector set.
    matrix = chooser.load_selection_matrix()
    all_cards = cards.expand_rows_to_cards(matrix.rows)
    got = {c.source_model_id: set(_sel(c)) for c in all_cards}
    assert got == EXPECTED_SELECTORS_BY_MODEL
    assert len(got) == 8
    assert len({cards.collection_id(c) for c in all_cards}) == 8  # ids stay unique


def test_every_collection_id_is_accepted_by_the_real_wandb_artifact():
    # 3.14. Do NOT assert against validate_artifact_name: verified that
    # Artifact.__init__ applies ^[a-zA-Z0-9_\-.]+$ BEFORE calling that validator, so
    # `=` is illegal too, and validate_artifact_name ACCEPTS an id the constructor
    # rejects. Asserting against the validator is a false green whose production
    # symptom is `--execute` raising on the first card. The constructor is public API,
    # offline, and needs no credential.
    import wandb

    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        name = cards.collection_id(card)
        wandb.Artifact(name=name, type="model")  # raises if illegal
        assert len(name) <= 128, (name, len(name))  # NAME_MAXLEN


def test_matrix_checksums_are_wellformed():
    import re

    matrix = chooser.load_selection_matrix()
    all_cards = cards.expand_rows_to_cards(matrix.rows)
    referenced = {c.source_model_id for c in all_cards}
    assert referenced == set(matrix.checksums)
    for model_id, sha in matrix.checksums.items():
        assert re.fullmatch(r"[0-9a-f]{64}", sha), (model_id, sha)


# --- 3.18: metadata survives wandb's own normalization unchanged ---


def test_card_to_metadata_is_serialization_stable():
    # The real wandb.Artifact normalizes metadata (tuple -> list, object -> dict,
    # pydantic model -> repr string) while the offline _FakeArtifact stores it
    # verbatim, so `art.metadata == card_to_metadata(card)` is a tautology that cannot
    # catch a degradation. Compare against the REAL constructor's stored metadata.
    import wandb

    matrix = chooser.load_selection_matrix()
    for card in cards.expand_rows_to_cards(matrix.rows):
        meta = cards.card_to_metadata(card)
        stored = wandb.Artifact(
            name=cards.collection_id(card), type="model", metadata=meta
        ).metadata
        assert json.loads(json.dumps(meta)) == stored
        # ...and the selector ORDER survives the round trip, not just the contents.
        assert [s["species"] for s in stored["selectors"]] == [
            s["species"] for s in meta["selectors"]
        ]
