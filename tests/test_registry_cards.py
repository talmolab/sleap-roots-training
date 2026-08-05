from collections import Counter

import pytest

from sleap_roots_training.registry import cards, chooser
from sleap_roots_training.registry.chooser import SelectionRow

CPA_PRIMARY = "canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743"
CANOLA_LATERAL = "canola/lateral/240611_083419.multi_instance.n=631"
ARABIDOPSIS_LATERAL = "arabidopsis/lateral/240130_140452.multi_instance.n=337"


def _row(species, mode, age, primary=None, lateral=None, crown=None):
    return SelectionRow(species, mode, age, primary, lateral, crown)


# --- Group 2: expansion shapes ---


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
    row = _row("rice", "cylinder", "6, 7, 8, 9, 10", crown="r/older/c")
    result = cards.expand_rows_to_cards([row])
    assert len(result) == 1
    assert result[0].root_type == "crown"
    assert result[0].age_min == 6 and result[0].age_max == 10


def test_primary_only_row_one_card():
    row = _row("soybean", "cylinder", "2, 3", primary="s/p")  # lateral+crown null
    result = cards.expand_rows_to_cards([row])
    assert len(result) == 1 and result[0].root_type == "primary"


def test_all_null_slots_produce_no_card():
    row = _row("soybean", "cylinder", "2, 3")  # all three model ids null
    assert cards.expand_rows_to_cards([row]) == []


# --- Group 2: shared-model expansion against the real matrix ---


def test_shared_primary_expands_to_four_distinct_cards():
    all_cards = cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    shared = [c for c in all_cards if c.source_model_id == CPA_PRIMARY]
    assert len(shared) == 4
    assert all(c.root_type == "primary" for c in shared)
    # Same source, but NOT identical: distinct (species, mode, age_max) triples.
    triples = Counter((c.species, c.mode, c.age_max) for c in shared)
    assert triples == Counter(
        {
            ("canola", "cylinder", 13): 1,
            ("pennycress", "cylinder", 14): 1,
            ("arabidopsis", "multiplant cylinder", 14): 1,
            ("arabidopsis", "cylinder", 14): 1,
        }
    )


def test_shared_laterals_expand_per_species():
    all_cards = cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    canola_lat = {c.species for c in all_cards if c.source_model_id == CANOLA_LATERAL}
    arab_lat = {
        (c.species, c.mode)
        for c in all_cards
        if c.source_model_id == ARABIDOPSIS_LATERAL
    }
    assert canola_lat == {"canola", "pennycress"}
    assert arab_lat == {
        ("arabidopsis", "multiplant cylinder"),
        ("arabidopsis", "cylinder"),
    }


def test_real_matrix_yields_thirteen_cards():
    all_cards = cards.expand_rows_to_cards(chooser.load_selection_matrix().rows)
    assert len(all_cards) == 13


# --- Group 3: metadata + collection ids ---


def test_card_to_metadata_exact_keys_and_raw_mode():
    card = cards.Card(
        "arabidopsis", "multiplant cylinder", 2, 14, "primary", CPA_PRIMARY
    )
    meta = cards.card_to_metadata(card)
    assert set(meta) == {
        "species",
        "mode",
        "age_min",
        "age_max",
        "root_type",
        "source_model_id",
    }
    # Intrinsics MUST NOT be present (the consumer injects them).
    assert not ({"registry_id", "version", "weights_checksum"} & set(meta))
    assert "sleap_nn_version" not in meta
    # Raw mode value preserved (space, NOT the hyphen slug) — the silent-break guard.
    assert meta["mode"] == "multiplant cylinder"


def test_metadata_validates_against_real_modelcard():
    from sleap_roots_contracts import ModelCard

    card = cards.Card("rice", "cylinder", 5, 5, "crown", "rice/older/c")  # age_min==max
    meta = cards.card_to_metadata(card)
    model_card = ModelCard.model_validate(
        {**meta, "registry_id": "rid", "version": "v1", "weights_checksum": "sha"}
    )
    assert model_card.sleap_nn_version is None  # despite extra source_model_id
    assert model_card.mode == "cylinder"


#: The vocabulary spelled out, NOT `sorted(chooser.MODE_VOCAB)`. Parametrizing over the
#: live set means an upstream *narrowing* silently shrinks the suite instead of failing
#: it: drop `"plate"` upstream and the `[plate]` case simply stops existing -- the suite
#: total drops by one and nothing is red. Spelled out, a narrowing is a failure. Keep in
#: sync with the literal witness in `test_registry_chooser.py` -- editing both is the
#: correct response to a deliberate vocabulary change.
_EXPECTED_MODES = ["cylinder", "multiplant cylinder", "plate"]


def test_expected_modes_match_the_live_vocabulary():
    assert set(_EXPECTED_MODES) == chooser.MODE_VOCAB
    assert len(_EXPECTED_MODES) == len(chooser.MODE_VOCAB)


@pytest.mark.parametrize("mode", _EXPECTED_MODES)
def test_every_accepted_mode_round_trips_through_the_real_modelcard(mode):
    # The loader accepting a mode is a set membership check; ModelCard accepting it is
    # an exact Literal match that normalizes neither case nor whitespace. The two can
    # diverge in the middle: if card_to_metadata ever emitted the hyphenated
    # collection-id slug ("multiplant-cylinder"), the loader would still pass and the
    # consumer would silently never match. Covers every mode, not just cylinder.
    from sleap_roots_contracts import ModelCard

    card = cards.Card("rice", mode, 2, 14, "primary", "r/p")
    meta = cards.card_to_metadata(card)
    model_card = ModelCard.model_validate(
        {**meta, "registry_id": "rid", "version": "v1", "weights_checksum": "sha"}
    )
    assert model_card.mode == mode  # raw value survives, unslugged and uncased


def test_every_committed_matrix_card_validates_against_the_real_modelcard():
    # The spec scenario ("published card metadata SHALL validate against ModelCard")
    # asserted on the real committed data rather than on synthetic cards. It matters that
    # this is a direct assertion: nothing in `src/` ever constructs a `ModelCard` --
    # `publish.py` writes `card_to_metadata` straight into `wandb.Artifact` -- so the
    # contract's validation is *only* ever exercised by tests on this side of the wire.
    # The consumer is where a bad card would otherwise first be noticed, which is too late.
    from sleap_roots_contracts import ModelCard

    matrix = chooser.load_selection_matrix()
    all_cards = cards.expand_rows_to_cards(matrix.rows)
    assert len(all_cards) == 13, "7 committed rows over 8 model ids -> 13 cards"

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
        assert model_card.mode == card.mode  # raw value survives, unslugged and uncased
        assert model_card.species == card.species


def test_collection_id_slugs_mode():
    card = cards.Card("arabidopsis", "multiplant cylinder", 2, 14, "lateral", "x")
    assert (
        cards.collection_id(card) == "arabidopsis-multiplant-cylinder-lateral-age2-14"
    )
    rice = cards.Card("rice", "cylinder", 6, 10, "crown", "y")
    assert cards.collection_id(rice) == "rice-cylinder-crown-age6-10"


# --- Group 3: offline matrix lock (guards data -> cards) ---

SOYBEAN_PRIMARY = "soybean/primary/221003_111420.multi_instance.n=1389"
SOYBEAN_LATERAL = "soybean/lateral/lateral_root_221006_172103.multi_instance.n=482"
RICE_Y_PRIMARY = "rice/younger/primary/230104_182346.multi_instance.n=720"
RICE_Y_CROWN = "rice/younger/crown/220821_163331.multi_instance.n=867"
RICE_O_CROWN = "rice/older/crown/221208_113552.multi_instance.n=574"

# Hand-transcribed from model_chooser_table.xlsx (NOT derived from the YAML under test).
EXPECTED_MODEL_BY_COLLECTION = {
    "soybean-cylinder-primary-age2-8": SOYBEAN_PRIMARY,
    "soybean-cylinder-lateral-age2-8": SOYBEAN_LATERAL,
    "canola-cylinder-primary-age2-13": CPA_PRIMARY,
    "canola-cylinder-lateral-age2-13": CANOLA_LATERAL,
    "pennycress-cylinder-primary-age2-14": CPA_PRIMARY,
    "pennycress-cylinder-lateral-age2-14": CANOLA_LATERAL,
    "arabidopsis-multiplant-cylinder-primary-age2-14": CPA_PRIMARY,
    "arabidopsis-multiplant-cylinder-lateral-age2-14": ARABIDOPSIS_LATERAL,
    "arabidopsis-cylinder-primary-age2-14": CPA_PRIMARY,
    "arabidopsis-cylinder-lateral-age2-14": ARABIDOPSIS_LATERAL,
    "rice-cylinder-primary-age2-5": RICE_Y_PRIMARY,
    "rice-cylinder-crown-age2-5": RICE_Y_CROWN,
    "rice-cylinder-crown-age6-10": RICE_O_CROWN,
}


def test_matrix_lock_collection_to_model():
    matrix = chooser.load_selection_matrix()
    all_cards = cards.expand_rows_to_cards(matrix.rows)
    got = {cards.collection_id(c): c.source_model_id for c in all_cards}
    assert got == EXPECTED_MODEL_BY_COLLECTION  # literal equality vs hard-coded RHS
    assert len(got) == 13  # all collection ids unique
    assert len(set(got.values())) == 8  # 8 distinct physical models


def test_matrix_checksums_are_wellformed():
    import re

    matrix = chooser.load_selection_matrix()
    # Every source model referenced by a card has a 64-hex checksum.
    all_cards = cards.expand_rows_to_cards(matrix.rows)
    referenced = {c.source_model_id for c in all_cards}
    assert referenced == set(matrix.checksums)
    for model_id, sha in matrix.checksums.items():
        assert re.fullmatch(r"[0-9a-f]{64}", sha), (model_id, sha)
