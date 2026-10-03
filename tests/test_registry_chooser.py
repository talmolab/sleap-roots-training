import pytest

from conftest import write_matrix
from sleap_roots_training.registry import chooser


def test_load_selection_matrix_has_nine_rows():
    matrix = chooser.load_selection_matrix()
    # 9 selection rows over 11 distinct model ids -> 11 cards (plate row omitted).
    assert len(matrix.rows) == 9
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
    # 11 distinct checksums, all 64-hex.
    assert len(matrix.checksums) == 11


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


def test_unreadable_matrix_is_a_valueerror_naming_the_path(tmp_path):
    # A directory reaches here: click's `--selection-matrix` type only checks existence.
    # `OmegaConf.load` then raises IsADirectoryError -- an OSError, not a ValueError --
    # which the `seed-registry` CLI does not catch, so the operator gets a traceback for
    # a plain "you pointed me at the wrong thing". Every way the file itself can be
    # unusable is normalized here, so callers have one exception type to wrap.
    with pytest.raises(ValueError, match="(?i)cannot read"):
        chooser.load_selection_matrix(tmp_path)


def test_missing_matrix_is_a_valueerror_naming_the_path(tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(ValueError, match="(?i)cannot read"):
        chooser.load_selection_matrix(missing)


def test_malformed_yaml_is_a_valueerror(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("models: [\n  - species: soybean\n")  # unterminated flow sequence
    # PyYAML raises ParserError (a yaml.YAMLError), which is neither ValueError nor
    # OSError -- the shape a hand-edited matrix fails in most often.
    with pytest.raises(ValueError, match="(?i)not valid yaml"):
        chooser.load_selection_matrix(bad)


def test_non_mapping_matrix_is_a_valueerror(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- species: soybean\n- species: canola\n")  # top level is a list
    # Without the type check this is `AttributeError: 'list' object has no attribute
    # 'get'` from inside the parse -- an implementation detail, not an operator message.
    with pytest.raises(ValueError, match="(?i)expected a mapping"):
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
    #
    # DO NOT "simplify" this away as a duplicate of the assertion above. `plate` is used
    # by none of the three authoring surfaces guarded in CI (the committed matrix,
    # `examples/`, `docs/training.md` all use only `cylinder` / `multiplant cylinder`),
    # so an upstream narrowing that dropped it would pass every one of them, and pass the
    # import guard too. Only a spelled-out literal catches that. The one in
    # `test_registry_cards.py` (`_EXPECTED_MODES`) is the other half of the same pair --
    # keep them in sync; editing both is the correct response to a deliberate vocabulary
    # change, and is where a human decides the change is intended, not accidental.
    assert chooser.MODE_VOCAB == {"cylinder", "multiplant cylinder", "plate"}


def test_mode_vocab_is_non_empty():
    # Defence in depth only, and honest about it: this cannot fail while it runs, because
    # `chooser` raises at import for the shapes it names, so the alternative to "trivially
    # true" is "not collected at all". It is kept so deleting the import guard in
    # `chooser` leaves something behind -- but note it does NOT survive a *weaker* guard,
    # which is the failure mode that actually happened once already. The guard's own
    # discrimination is tested by `test_chooser_refuses_to_import_...` below.
    assert chooser.MODE_VOCAB
    assert all(isinstance(mode, str) for mode in chooser.MODE_VOCAB)


def test_root_type_vocab_is_the_contract_vocabulary_unforked():
    # The same single-owner rule as `MODE_VOCAB`, for the vocabulary that had *three*
    # local copies before this: `config.ROOT_TYPE_VOCAB`, `labeling/metadata`'s
    # `ROOT_TYPE_VOCAB`, and -- as a set -- `cards._ROOT_SLOTS`. Three hand-maintained
    # mirrors of one contract literal are three chances to drift, and the guard that
    # existed only compared two of them to *each other*, which passes just as happily
    # when both are wrong.
    from typing import get_args

    from sleap_roots_contracts import RootType

    assert chooser.ROOT_TYPE_VOCAB == frozenset(get_args(RootType))
    # The independent witness, for the reason spelled out in the `Mode` test above: the
    # assertion on the line before re-derives the set exactly the way production does, so
    # it passes when `get_args()` returns `()` on both sides. Only a spelled-out literal
    # catches an upstream *narrowing*. `crown` is the member at risk -- it reaches the
    # committed matrix on rice rows only, and `examples/` uses `primary`, so a narrowing
    # that dropped it would leave the authoring surfaces green. Editing this literal is
    # where a human confirms a vocabulary change is intended; do not "simplify" it into
    # another re-derivation. Its counterpart is `_EXPECTED_ROOT_SLOTS` in
    # `test_registry_cards.py` -- keep the two in sync.
    assert chooser.ROOT_TYPE_VOCAB == {"primary", "lateral", "crown"}


def test_root_type_vocab_is_non_empty():
    # Defence in depth, and as honest about it as its `MODE_VOCAB` twin: this cannot fail
    # while it runs, because `chooser` raises at import for the shapes it names. It is
    # kept so that deleting the import guard leaves something behind.
    assert chooser.ROOT_TYPE_VOCAB
    assert all(isinstance(root_type, str) for root_type in chooser.ROOT_TYPE_VOCAB)


def test_species_vocab_stays_local():
    # The mirror of the above: a *selector's* species is a free `str`, so there is no
    # contract-side species vocabulary to defer to. Guards against a future reader
    # assuming both constants moved.
    import sleap_roots_contracts
    from sleap_roots_contracts import ModelCard, Selector

    assert "soybean" in chooser.SPECIES_VOCAB
    # The actual invariant, asserted on the field rather than on a symbol name: a
    # contract-side species vocabulary would arrive the way `Mode` did -- as a Literal
    # annotation on the species field -- which a `hasattr(..., "Species")` probe would
    # not see. The symbol check stays as the secondary signal.
    assert Selector.model_fields["species"].annotation is str
    assert not hasattr(sleap_roots_contracts, "Species")
    # And it really did move: the card no longer carries species at all, so a reader
    # reaching for ModelCard.species gets a loud KeyError rather than a stale answer.
    assert "species" not in ModelCard.model_fields


def test_wheat_and_sorghum_are_in_the_species_vocabulary():
    # talmolab/sleap-roots-training#72: the consumer receives Bloom's common name
    # lowercased by bloomctl, so these are the exact strings predict will match.
    assert {"wheat", "sorghum"} <= chooser.SPECIES_VOCAB


def test_a_matrix_with_wheat_and_sorghum_rows_loads(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(
        "models:\n"
        "  - species: wheat\n"
        "    mode: cylinder\n"
        '    age: "5, 6"\n'
        "    crown_model_id: w/c/1\n"
        '    source: "test row"\n'
        "  - species: sorghum\n"
        "    mode: cylinder\n"
        '    age: "3, 4"\n'
        "    primary_model_id: s/p/1\n"
        '    source: "test row"\n'
        "origins:\n"
        '  w/c/1: {snapshot: null, location: "test location", pinned_by: "test pin"}\n'
        '  s/p/1: {snapshot: null, location: "test location", pinned_by: "test pin"}\n'
    )
    matrix = chooser.load_selection_matrix(path)
    assert [row.species for row in matrix.rows] == ["wheat", "sorghum"]


def test_every_species_is_a_lowercase_common_name():
    # Predict and the traits chooser compare species by plain string equality against
    # a lowercased Bloom common name, so a capitalized member would never match.
    assert all(species == species.lower() for species in chooser.SPECIES_VOCAB)


def test_an_unlisted_crop_is_still_rejected(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(
        "models:\n"
        "  - species: alfalfa\n"
        "    mode: cylinder\n"
        '    age: "3"\n'
        "    primary_model_id: a/p/1\n"
    )
    with pytest.raises(ValueError, match="row 0: unknown species 'alfalfa'"):
        chooser.load_selection_matrix(path)


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


# --- the import-time guard ------------------------------------------------------------
#
# Exercised in a subprocess against a stub `sleap_roots_contracts` on PYTHONPATH, because
# the thing under test happens at module import: it cannot be reached by monkeypatching a
# module that has already imported successfully, and re-importing `chooser` in-process
# would leave a half-initialized module in `sys.modules` for every later test.

_STUB_HEADER = (
    "from enum import Enum\n"
    "from typing import Annotated, Literal, Optional, Union\n"
    "from pydantic import Field\n"
)

#: Upstream reshapes of `Mode` that `typing.get_args()` destructures *without* raising.
#: Only the first two are empty -- which is why the guard cannot be an emptiness check.
#: `Annotated[..., Field(...)]` is the realistic one for a pydantic-first contracts
#: package; `Optional` arrives the moment a card may carry an unknown mode; a `Union` of
#: `Literal`s arrives when a vocabulary is split into sub-families.
_MODE_RESHAPES = {
    "enum": "class Mode(str, Enum):\n    CYLINDER = 'cylinder'\n",
    "str_alias": "Mode = str\n",
    "annotated": "Mode = Annotated[Literal['cylinder', 'plate'], Field()]\n",
    "optional": "Mode = Optional[Literal['cylinder', 'plate']]\n",
    "union": "Mode = Union[Literal['cylinder'], Literal['plate']]\n",
    # `Annotated`'s metadata slot takes *any* object, not just a hashable one. This shape
    # is what made the guard build its frozenset before type-checking a fault: hashing an
    # unhashable member raises TypeError from inside the guard, so the import dies without
    # naming the alias or the constant -- the same "error while reporting the error" the
    # `sorted()` note in `chooser` warns about.
    "unhashable_annotated": (
        "Mode = Annotated[Literal['cylinder', 'plate'], {'deprecated': True}]\n"
    ),
}

#: The same six reshapes for `RootType`, which `chooser` now also derives a vocabulary
#: from. Kept as a separate table rather than generated from `_MODE_RESHAPES` by string
#: substitution: the members differ, and a generated table would silently stop covering a
#: shape the moment the two aliases diverge upstream.
_ROOT_TYPE_RESHAPES = {
    "enum": "class RootType(str, Enum):\n    PRIMARY = 'primary'\n",
    "str_alias": "RootType = str\n",
    "annotated": "RootType = Annotated[Literal['primary', 'lateral'], Field()]\n",
    "optional": "RootType = Optional[Literal['primary', 'lateral']]\n",
    "union": "RootType = Union[Literal['primary'], Literal['lateral']]\n",
    "unhashable_annotated": (
        "RootType = Annotated[Literal['primary', 'lateral'], {'deprecated': True}]\n"
    ),
}

#: The healthy shape of each alias. One reshape is injected at a time, against a valid
#: counterpart, so a failure names which alias the guard caught -- a stub that reshaped
#: both would pass the assertions for the wrong reason.
_VALID_MODE = "Mode = Literal['cylinder', 'multiplant cylinder', 'plate']\n"
_VALID_ROOT_TYPE = "RootType = Literal['primary', 'lateral', 'crown']\n"


def _import_chooser_with_stub_contracts(
    tmp_path, *, mode_source=_VALID_MODE, root_type_source=_VALID_ROOT_TYPE
):
    """Import ``chooser`` in a subprocess against a stubbed ``sleap_roots_contracts``."""
    import os
    import subprocess
    import sys

    stub = tmp_path / "sleap_roots_contracts"
    stub.mkdir()
    (stub / "__init__.py").write_text(
        _STUB_HEADER + mode_source + root_type_source, encoding="utf-8"
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp_path)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", "import sleap_roots_training.registry.chooser"],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("shape", sorted(_MODE_RESHAPES))
def test_chooser_refuses_to_import_when_mode_is_not_a_literal_of_strings(
    shape, tmp_path
):
    # The whole point of the guard is that it fails *at the seam*, naming what changed,
    # instead of letting every real mode start getting rejected somewhere downstream.
    result = _import_chooser_with_stub_contracts(
        tmp_path, mode_source=_MODE_RESHAPES[shape]
    )

    assert result.returncode != 0, f"{shape}: chooser imported anyway\n{result.stdout}"
    assert "RuntimeError" in result.stderr
    # The message must name the culprit and must not crash while reporting it -- an
    # earlier draft sorted() the members, which raises TypeError on the mixed-type
    # shapes and buries the diagnosis under an error from the error path.
    assert "sleap_roots_contracts.Mode" in result.stderr
    assert "TypeError" not in result.stderr


@pytest.mark.parametrize("shape", sorted(_ROOT_TYPE_RESHAPES))
def test_chooser_refuses_to_import_when_root_type_is_not_a_literal_of_strings(
    shape, tmp_path
):
    # `ROOT_TYPE_VOCAB` is derived the same way as `MODE_VOCAB` and degrades the same
    # way, so it carries the same guard -- and that guard needs its own fault injection,
    # not inherited confidence from the `Mode` case. A single shared helper covering both
    # aliases can still be wired up for only one of them.
    result = _import_chooser_with_stub_contracts(
        tmp_path, root_type_source=_ROOT_TYPE_RESHAPES[shape]
    )

    assert result.returncode != 0, f"{shape}: chooser imported anyway\n{result.stdout}"
    assert "RuntimeError" in result.stderr
    # Naming the *right* alias is the point: an error blaming `Mode` for a reshaped
    # `RootType` sends the reader to the wrong upstream symbol.
    assert "sleap_roots_contracts.RootType" in result.stderr
    assert "sleap_roots_contracts.Mode" not in result.stderr
    # Both of `_vocab_from_contract_literal`'s naming arguments are swappable independently:
    # the pair above catches a swapped `name`, this pair a swapped `vocab_name`. Without it,
    # a call passing `RootType` but labelling the constant `MODE_VOCAB` reads as correct.
    assert "ROOT_TYPE_VOCAB" in result.stderr
    assert "MODE_VOCAB" not in result.stderr
    assert "TypeError" not in result.stderr


def test_chooser_imports_cleanly_when_both_aliases_are_plain_literals(tmp_path):
    # The negative control: the guard must discriminate, not just fail. Without this,
    # a guard of `if True:` would pass every assertion above.
    result = _import_chooser_with_stub_contracts(tmp_path)
    assert result.returncode == 0, result.stderr


# --- Model-id type validation (review note, PR #47) ---


@pytest.mark.parametrize(
    "bad", ["743", "[743]", "true", "{a: b}"], ids=["int", "list", "bool", "mapping"]
)
def test_a_non_string_model_id_is_rejected_with_a_row_numbered_error(tmp_path, bad):
    # An unquoted `n=743`-style id, a stray list, a bare `true`, or a nested mapping all
    # parse to non-strings. Before this check they passed every row validation and blew
    # up much later as an opaque AttributeError inside cards.collection_id, at
    # --execute time -- unlike every other malformed-row case, which fails here.
    path = tmp_path / "matrix.yaml"
    path.write_text(
        "models:\n"
        "  - species: soybean\n"
        "    mode: cylinder\n"
        '    age: "2, 3"\n'
        f"    primary_model_id: {bad}\n"
        "    lateral_model_id: null\n"
        "    crown_model_id: null\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        chooser.load_selection_matrix(path)
    message = str(excinfo.value)
    assert "row 0" in message
    assert "primary_model_id" in message


def test_a_string_model_id_and_an_absent_one_are_both_accepted(tmp_path):
    # The negative control: the guard must discriminate. A quoted id and a null slot
    # are the normal cases and must survive.
    path = tmp_path / "matrix.yaml"
    path.write_text(
        "models:\n"
        "  - species: soybean\n"
        "    mode: cylinder\n"
        '    age: "2, 3"\n'
        "    primary_model_id: soybean/primary/221003_111420.multi_instance.n=1389\n"
        "    lateral_model_id: null\n"
        "    crown_model_id: null\n"
        '    source: "test row"\n'
        "origins:\n"
        "  soybean/primary/221003_111420.multi_instance.n=1389:\n"
        '    {snapshot: null, location: "test location", pinned_by: "test pin"}\n',
        encoding="utf-8",
    )
    matrix = chooser.load_selection_matrix(path)
    assert len(matrix.rows) == 1
    assert matrix.rows[0].primary_model_id.endswith("n=1389")
    assert matrix.rows[0].lateral_model_id is None


# --- Selection Matrix Provenance (add-wheat-sorghum-production-cards) ---

_ROW = {
    "species": "soybean",
    "mode": "cylinder",
    "age": "2, 3",
    "primary_model_id": "m/p",
}
_ROW_2 = {"species": "rice", "mode": "cylinder", "age": "2", "crown_model_id": "m/c"}


def _load(tmp_path, rows=(_ROW,), **kw):
    return chooser.load_selection_matrix(
        write_matrix(tmp_path / "m.yaml", list(rows), **kw)
    )


@pytest.mark.parametrize(
    "case, kw",
    [
        ("missing", {"drop": [("row", 0, "source")]}),
        ("empty", {"override": {("row", 0, "source"): ""}}),
        ("not a string", {"override": {("row", 0, "source"): 5}}),
    ],
)
def test_a_row_without_a_valid_source_is_rejected(tmp_path, case, kw):
    with pytest.raises(ValueError, match=r"row 0.*source"):
        _load(tmp_path, **kw)


@pytest.mark.parametrize(
    "case, kw, needle",
    [
        ("no entry", {"drop": [("origin", "m/p")]}, "m/p"),
        ("no location", {"drop": [("origin", "m/p", "location")]}, "location"),
        (
            "empty location",
            {"override": {("origin", "m/p", "location"): ""}},
            "location",
        ),
        ("no pinned_by", {"drop": [("origin", "m/p", "pinned_by")]}, "pinned_by"),
        (
            "int pinned_by",
            {"override": {("origin", "m/p", "pinned_by"): 5}},
            "pinned_by",
        ),
        # An unquoted `snapshot: 20250204` parses as an int, not the string it means.
        (
            "int snapshot",
            {"override": {("origin", "m/p", "snapshot"): 20250204}},
            "snapshot",
        ),
        # An omitted key would otherwise read as None -- a silent "ships in no snapshot".
        ("no snapshot key", {"drop": [("origin", "m/p", "snapshot")]}, "snapshot"),
        ("scalar entry", {"origins": {"m/p": "somewhere"}}, "m/p"),
    ],
)
def test_a_referenced_model_with_a_missing_or_mistyped_origin_is_rejected(
    tmp_path, case, kw, needle
):
    with pytest.raises(ValueError) as excinfo:
        _load(tmp_path, **kw)
    assert "m/p" in str(excinfo.value)
    assert needle in str(excinfo.value)


@pytest.mark.parametrize(
    "kw", [{"drop": [("origins",)]}, {"origins": None}], ids=["absent", "null"]
)
def test_no_origins_map_reports_the_first_uncovered_model(tmp_path, kw):
    with pytest.raises(ValueError, match="m/p"):
        _load(tmp_path, **kw)


def test_an_origins_list_is_rejected_naming_origins(tmp_path):
    with pytest.raises(ValueError, match="origins"):
        _load(tmp_path, origins=["m/p"])


def test_an_origin_for_an_unreferenced_model_is_rejected_as_stale(tmp_path):
    stale = {"snapshot": None, "location": "x", "pinned_by": "y"}
    with pytest.raises(ValueError, match=r"(?i)stale.*gone/model|gone/model.*stale"):
        _load(
            tmp_path,
            override={("origin", "gone/model", k): v for k, v in stale.items()},
        )


def test_coverage_is_checked_only_after_every_row(tmp_path):
    # Row 0's model has no origin AND row 1 has no source: the per-row check on row 1
    # must win, because origin coverage runs only once every row is read.
    with pytest.raises(ValueError, match=r"row 1.*source"):
        _load(
            tmp_path,
            rows=(_ROW, _ROW_2),
            drop=[("origin", "m/p"), ("row", 1, "source")],
        )


@pytest.mark.parametrize(
    "override, needle",
    [
        ({("row", 0, "species"): "alfalfa"}, "alfalfa"),
        ({("row", 0, "primary_model_id"): 5}, "primary_model_id"),
    ],
    ids=["vocabulary", "model-id type"],
)
def test_earlier_row_checks_report_before_the_source_check(tmp_path, override, needle):
    with pytest.raises(ValueError, match=needle):
        _load(tmp_path, override=override, drop=[("row", 0, "source")], origins={})


def test_origins_parse_into_records(tmp_path):
    matrix = _load(
        tmp_path,
        rows=(_ROW, _ROW_2),
        override={("origin", "m/c", "snapshot"): "20250204"},
    )
    assert matrix.rows[0].source == "test row 0"
    assert matrix.origins["m/p"] == chooser.ModelOrigin(
        snapshot=None, location="test location", pinned_by="test pin"
    )
    assert matrix.origins["m/c"].snapshot == "20250204"


def test_every_committed_row_has_a_source_and_origins_cover_exactly_its_models():
    matrix = chooser.load_selection_matrix()
    assert all(isinstance(r.source, str) and r.source for r in matrix.rows)
    referenced = {
        model_id
        for row in matrix.rows
        for model_id in (row.primary_model_id, row.lateral_model_id, row.crown_model_id)
        if model_id is not None
    }
    assert set(matrix.origins) == referenced


def test_committed_origins_name_no_share_path():
    # This repo is public: a location is relative to a run or a snapshot, never a share
    # path naming a machine or its owner.
    backslash = chr(92)
    for model_id, origin in chooser.load_selection_matrix().origins.items():
        location = origin.location
        assert not location.startswith("/"), model_id
        for banned in (":" + backslash, backslash * 2, "hpi", "users/"):
            assert banned not in location, (model_id, banned)


# --- the wheat and sorghum rows (talmolab/sleap-roots-training#72) ---

WHEAT_CROWN = "20250401_wheat_models/250328_095645.multi_instance.n=1658"
SORGHUM_PRIMARY = "20250204_sorghum_experimental/sorghum_soybean_primary_6nodes/250203_181521.multi_instance.n=1689"
SORGHUM_LATERAL = "20250204_sorghum_experimental/sorghum_soybean_lateral_4nodes/250203_214033.multi_instance.n=590"


def test_the_wheat_and_sorghum_source_zips_are_pinned_to_their_measured_digests():
    # Recomputed from the zips on hpi_dev on 2026-10-03; they match training#72.
    checksums = chooser.load_selection_matrix().checksums
    assert checksums[WHEAT_CROWN] == (
        "650fe30ba2d61e0a292c6dbeaac531a655e811e551bae8c4d9bef0b5f51ba13f"
    )
    assert checksums[SORGHUM_PRIMARY] == (
        "7c2cd05ded5b3f80163ccd171f3b4abb074ba609f4d52473799162ab763a7c07"
    )
    assert checksums[SORGHUM_LATERAL] == (
        "f694d6da5a71b17ad72a48c308916ea7d95c5cb9a5c7fcdfe619e59c90130028"
    )


def test_wheat_ships_in_no_snapshot_and_sorghum_in_the_20250204_one():
    origins = chooser.load_selection_matrix().origins
    assert origins[WHEAT_CROWN].snapshot is None
    assert origins[SORGHUM_PRIMARY].snapshot == "20250204"
    assert origins[SORGHUM_LATERAL].snapshot == "20250204"
