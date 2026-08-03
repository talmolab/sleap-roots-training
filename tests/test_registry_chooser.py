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
    # Deliberately NOT re-derived via get_args: that is how production builds the set, so
    # comparing the two only proves they agree, including when both are empty. If `Mode`
    # stops being a `Literal`, get_args() returns () on both sides and the check above
    # still passes. This literal is the independent witness.
    assert chooser.MODE_VOCAB == {"cylinder", "multiplant cylinder", "plate"}


def test_mode_vocab_is_non_empty():
    # The degradation the assertion above cannot see on its own: get_args() returns ()
    # rather than raising for a non-parameterized type, so an upstream Literal -> Enum
    # change would silently mean "no mode is valid". chooser raises at import for this;
    # keep a named test so the intent survives a refactor of that guard.
    assert chooser.MODE_VOCAB


def test_species_vocab_stays_local():
    # The mirror of the above: ModelCard.species is a free `str`, so there is no
    # contract-side species vocabulary to defer to. Guards against a future reader
    # assuming both constants moved.
    import sleap_roots_contracts
    from sleap_roots_contracts import ModelCard

    assert "soybean" in chooser.SPECIES_VOCAB
    # The actual invariant, asserted on the field rather than on a symbol name: a
    # contract-side species vocabulary would arrive the way `Mode` did -- as a Literal
    # annotation on ModelCard.species -- which a `hasattr(..., "Species")` probe would
    # not see. The symbol check stays as the secondary signal.
    assert ModelCard.model_fields["species"].annotation is str
    assert not hasattr(sleap_roots_contracts, "Species")


def test_every_committed_matrix_mode_is_contract_valid():
    """The spec scenario, asserted against the committed file rather than the loader.

    Reading via ``load_selection_matrix`` would be vacuous: the loader already rejects a
    row whose mode is outside ``MODE_VOCAB``, so anything reachable through
    ``matrix.rows`` satisfies this by construction. Parsing the YAML directly is what
    makes it a real check on the *data* — it fails if a row is committed with a bad mode
    and the loader's guard is ever loosened, which is the pair the scenario is about.
    """
    from importlib.resources import as_file, files
    from typing import get_args

    from omegaconf import OmegaConf
    from sleap_roots_contracts import Mode

    resource = files(chooser._DATA_PACKAGE).joinpath(chooser._DATA_RESOURCE)
    with as_file(resource) as path:
        raw = OmegaConf.load(path)

    modes = [row["mode"] for row in raw["models"]]
    assert modes, "committed selection matrix has no rows"
    for mode in modes:
        assert mode in get_args(Mode), f"committed mode {mode!r} is out of vocabulary"
