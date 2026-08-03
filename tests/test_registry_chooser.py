import pytest

from sleap_roots_training.registry import chooser


def test_load_selection_matrix_has_seven_rows():
    matrix = chooser.load_selection_matrix()
    # 7 selection rows over 8 distinct model ids -> 13 cards (plate row omitted).
    assert len(matrix.rows) == 7
    # spot-check the shared primary + a crown-only row.
    by_species_mode = {(r.species, r.mode): r for r in matrix.rows}
    canola = by_species_mode[("canola", "cylinder")]
    assert (
        canola.primary_model_id
        == "canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743"
    )
    assert canola.crown_model_id is None
    rice_old = by_species_mode[("rice", "cylinder")]  # last rice row wins in dict
    assert rice_old.primary_model_id is None and rice_old.lateral_model_id is None
    # 8 distinct checksums, all 64-hex.
    assert len(matrix.checksums) == 8


def test_parse_age_window_range():
    assert chooser.parse_age_window("2, 3, 4, 5, 6, 7, 8") == (2, 8)


def test_parse_age_window_single():
    assert chooser.parse_age_window("5") == (5, 5)


def test_parse_age_window_gap_raises():
    with pytest.raises(ValueError, match="gap|contiguous|3, 5"):
        chooser.parse_age_window("2, 3, 5")


def test_parse_age_window_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        chooser.parse_age_window("")


def test_missing_required_key_raises_indexed(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(  # row 0 has no `age`
        "models:\n"
        "  - species: soybean\n"
        "    mode: cylinder\n"
        "    primary_model_id: x/p/1\n"
        "checksums:\n"
        "  x/p/1: " + "0" * 64 + "\n"
    )
    with pytest.raises(ValueError, match="row 0.*age"):
        chooser.load_selection_matrix(bad)


def test_empty_models_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("model:\n  - {}\n")  # typo'd top-level key -> no rows
    with pytest.raises(ValueError, match="(?i)no .*models"):
        chooser.load_selection_matrix(bad)


def test_unknown_species_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "models:\n"
        "  - species: turnip\n"
        "    mode: cylinder\n"
        '    age: "2, 3"\n'
        "    primary_model_id: x/p/1\n"
        "    lateral_model_id: null\n"
        "    crown_model_id: null\n"
        "checksums:\n"
        "  x/p/1: " + "0" * 64 + "\n"
    )
    with pytest.raises(ValueError, match="turnip"):
        chooser.load_selection_matrix(bad)


def test_unknown_mode_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "models:\n"
        "  - species: soybean\n"
        "    mode: teacup\n"
        '    age: "2, 3"\n'
        "    primary_model_id: x/p/1\n"
        "    lateral_model_id: null\n"
        "    crown_model_id: null\n"
        "checksums:\n"
        "  x/p/1: " + "0" * 64 + "\n"
    )
    with pytest.raises(ValueError, match="teacup"):
        chooser.load_selection_matrix(bad)


def test_mode_vocab_is_the_contract_vocabulary_unforked():
    # The mode vocabulary has exactly one owner: sleap-roots-contracts. This fails if
    # it is ever re-forked locally (say, `frozenset(get_args(Mode)) | {"cyl"}` added to
    # let a stray value load) -- which is precisely how producer and consumer drift
    # apart with no error raised anywhere until a scan silently matches no model.
    from typing import get_args

    from sleap_roots_contracts import Mode

    assert chooser.MODE_VOCAB == frozenset(get_args(Mode))


def test_species_vocab_stays_local():
    # The mirror of the above: ModelCard.species is a free `str`, so there is no
    # contract-side species vocabulary to defer to. Guards against a future reader
    # assuming both constants moved.
    assert "soybean" in chooser.SPECIES_VOCAB
    assert not hasattr(__import__("sleap_roots_contracts"), "Species")
