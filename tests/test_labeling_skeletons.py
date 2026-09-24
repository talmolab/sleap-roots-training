"""Tests for the committed per-crop labeling skeleton table (design.md Decision 7).

The cylinder rows are transcribed from an advisory source that says of itself "Query the
Bloom database or check existing test data ... to confirm node counts", so these tests pin
that a gap fails loudly rather than defaulting, and cross-check the parts of the table that
have an independent source in this repo: the rice age split, which
``registry/data/model_selection.yaml`` already encodes, and the arabidopsis plate row,
which the committed label inventory (``inventory/label-inventory.csv``) evidences.

The verification against the eight published collections lives at the bottom, marked
``integration``: it is what converts the rest of the table from hypothesis to record, and
it downloads multi-gigabyte artifacts, so it is not part of the default run.
"""

from __future__ import annotations

import collections
import csv
import os
from pathlib import Path
from typing import Optional

import pytest

from sleap_roots_training.labeling.skeletons import (
    load_skeleton_table,
    lookup_skeleton,
    skeleton_table_sha256,
)
from sleap_roots_training.registry.chooser import (
    MODE_VOCAB,
    load_selection_matrix,
    parse_age_window,
)


def write_table(tmp_path, body: str):
    """Write a skeleton-table YAML and return its path."""
    path = tmp_path / "skeletons.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# The committed table
# --------------------------------------------------------------------------------------


def test_the_committed_table_loads_and_is_hashable():
    """The SHA is what pins which table a package was built against, as for the matrix."""
    rows = load_skeleton_table()

    assert rows
    assert len(skeleton_table_sha256()) == 64


@pytest.mark.parametrize(
    "species, root_type, node_count",
    [
        ("soybean", "primary", 6),
        ("soybean", "lateral", 4),
        ("canola", "primary", 6),
        ("canola", "lateral", 3),
        ("arabidopsis", "primary", 6),
        ("arabidopsis", "lateral", 4),
    ],
)
def test_the_doc_table_is_transcribed_faithfully(species, root_type, node_count):
    """Row-for-row against the Box snapshot's ``build-labeling-package.md:45-51``.

    That source covers cylinder only, so every row it gave is ``mode: cylinder``.

    Canola's lateral 3 is deliberately included as-is: it is the table's one asymmetry —
    soybean and arabidopsis laterals are both 4 — and transcribing it accurately is what
    lets the verification test find out whether it is real.
    """
    assert lookup_skeleton(species, root_type, mode="cylinder").node_count == node_count


def test_soybean_matches_the_real_published_artifacts():
    """Verified 2026-08-04 against the WEEP v000 projects and their repaired packages.

    Those files carry ``soybean_primary`` r1-r6 and ``soybean_lateral`` r1-r4, so these
    two rows are record rather than hypothesis. The artifacts are not committed (hundreds
    of MB), so this test pins the *finding*; the integration test below is what re-derives
    it from the registry.
    """
    assert lookup_skeleton("soybean", "primary").node_count == 6
    assert lookup_skeleton("soybean", "lateral").node_count == 4


def test_node_names_and_edges_follow_the_fixed_convention():
    """``r1`` is the base, the last node is the tip, and the edges are a simple chain."""
    skeleton = lookup_skeleton("soybean", "primary").to_skeleton()

    assert [node.name for node in skeleton.nodes] == [
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
        "r6",
    ]
    assert skeleton.name == "soybean_primary"
    assert len(skeleton.edges) == 5


def test_the_skeleton_name_matches_what_the_vault_script_wrote():
    """A new package's skeleton has to be recognizable as the same one the corpus uses."""
    assert lookup_skeleton("soybean", "lateral").to_skeleton().name == "soybean_lateral"


# --------------------------------------------------------------------------------------
# add-skeleton-mode — Committed Skeleton Rows Carry Their Mode
# --------------------------------------------------------------------------------------

#: The committed scan (#58). Resolved from this file, not the working directory, so the
#: evidence check runs the same from any cwd. It is committed, so absence is a failure.
_INVENTORY_CSV = (
    Path(__file__).resolve().parents[1] / "inventory" / "label-inventory.csv"
)


def _plate_row():
    matches = [
        r
        for r in load_skeleton_table()
        if (r.species, r.mode, r.root_type) == ("arabidopsis", "plate", "primary")
    ]
    assert len(matches) == 1, f"expected one arabidopsis plate primary row: {matches}"
    return matches[0]


def test_every_transcribed_row_is_cylinder():
    """Characterisation: the onboarding doc every other row came from is cylinder-only."""
    others = [
        r
        for r in load_skeleton_table()
        if (r.species, r.mode, r.root_type) != ("arabidopsis", "plate", "primary")
    ]
    assert others
    assert {r.mode for r in others} == {"cylinder"}


def test_the_plate_row_is_unverified():
    """Landed unverified by decision, and stays so until a person flips it.

    The published collection agrees when read by hand (8 nodes, 2026-09-24), but the
    automated published-collections check cannot resolve any collection yet (#64), and
    the mode is read off directory names. So a plate build still warns.
    """
    assert _plate_row().verified is False


@pytest.mark.parametrize("age, expected", [(1, None), (2, 8), (7, 8), (8, None)])
def test_the_plate_lookup_has_exact_bounds(age, expected):
    """The evidence covers 2-7 exactly; a lookup outside it lists the window."""
    if expected is None:
        with pytest.raises(ValueError, match="2-7 DAG"):
            lookup_skeleton("arabidopsis", "primary", age=age, mode="plate")
    else:
        row = lookup_skeleton("arabidopsis", "primary", age=age, mode="plate")
        assert row.node_count == expected
    # The cylinder row is untouched by the plate one.
    cylinder = lookup_skeleton("arabidopsis", "primary", age=age, mode="cylinder")
    assert cylinder.node_count == 6


def _node_count_families(csv_path, key):
    """Count labelled families per node count for one ``(species, mode, root_type)``.

    Families with no user instances are prediction-only copies and are left out.
    """
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return collections.Counter(
            int(row["node_count"])
            for row in csv.DictReader(handle)
            if (row["species"], row["mode"], row["root_type"]) == key
            and row["node_count"]
            and int(row["user_instances"] or 0) > 0
        )


def _is_strict_plurality(families_by_count, node_count):
    """Whether ``node_count`` has strictly more families than every other count."""
    return families_by_count[node_count] > 0 and all(
        families > 0 and families_by_count[node_count] > families
        for other, families in families_by_count.items()
        if other != node_count
    )


def test_a_tie_or_a_minority_is_not_a_strict_plurality(tmp_path):
    """The evidence check has to be able to fail; a tie is not agreement."""
    header = "species,mode,root_type,node_count,user_instances\n"
    rows = "".join(
        f"arabidopsis,plate,primary,{count},10\n" for count in (8, 8, 7, 7, 6)
    )
    path = tmp_path / "label-inventory.csv"
    path.write_text(header + rows, encoding="utf-8")
    counts = _node_count_families(path, ("arabidopsis", "plate", "primary"))

    assert counts == {8: 2, 7: 2, 6: 1}
    assert not _is_strict_plurality(counts, 8)
    assert not _is_strict_plurality(counts, 6)
    assert _is_strict_plurality(collections.Counter({8: 3, 7: 2}), 8)


def test_the_plate_row_agrees_with_the_committed_scan():
    """The row's node count is the strict plurality in the committed inventory.

    Read, never re-scanned. Families with no user instances are prediction-only copies
    and are left out. A later scan that moves the evidence fails here instead of
    silently diverging from the table; CI's path filter includes ``inventory/**`` so a
    re-scan PR runs this.
    """
    assert _INVENTORY_CSV.is_file(), f"committed evidence missing: {_INVENTORY_CSV}"
    counts = _node_count_families(_INVENTORY_CSV, ("arabidopsis", "plate", "primary"))

    expected = _plate_row().node_count
    assert counts, "the committed scan has no labelled arabidopsis plate primary family"
    assert _is_strict_plurality(
        counts, expected
    ), f"{expected} is not the strict plurality: {dict(counts)}"


# --------------------------------------------------------------------------------------
# Task 6.3 — a gap fails loudly
# --------------------------------------------------------------------------------------


def test_pennycress_has_no_row_and_fails_rather_than_defaulting():
    """The table ships incomplete on purpose; the source omits pennycress.

    Pennycress is in ``SPECIES_VOCAB`` and has two ``model_selection.yaml`` rows, so a
    caller can reach this. Defaulting to canola's counts — which share a primary model —
    would produce a labeling package that looks fine and cannot be combined with anything.
    """
    with pytest.raises(ValueError) as excinfo:
        lookup_skeleton("pennycress", "primary")

    assert "pennycress" in str(excinfo.value)
    # The error lists what the table does cover, so the reader can see the gap is real.
    assert "soybean" in str(excinfo.value)


def test_a_root_type_the_species_does_not_have_fails():
    """Soybean has no crown row, and inventing one would invent a skeleton."""
    with pytest.raises(ValueError, match="crown"):
        lookup_skeleton("soybean", "crown")


def test_rice_lateral_has_no_row():
    """``model_selection.yaml`` has no rice lateral model either — the two agree."""
    with pytest.raises(ValueError, match="lateral"):
        lookup_skeleton("rice", "lateral", age=3)


# --------------------------------------------------------------------------------------
# Task 6.4 — the rice age split cross-checked against model_selection.yaml
# --------------------------------------------------------------------------------------


def rice_matrix_rows():
    """Return ``{age_window: {root_type, ...}}`` from the committed selection matrix."""
    windows = {}
    for row in load_selection_matrix().rows:
        if row.species != "rice":
            continue
        present = {
            root_type
            for root_type, model_id in (
                ("primary", row.primary_model_id),
                ("lateral", row.lateral_model_id),
                ("crown", row.crown_model_id),
            )
            if model_id
        }
        windows[parse_age_window(row.age)] = present
    return windows


def test_the_rice_age_split_agrees_between_the_two_tables():
    """Young 2-5 DAG is primary + crown; old 6-10 DAG is crown only.

    These tables are transcribed from different sources — the skeleton table from the
    command doc, the matrix from ``models-downloader``'s chooser xlsx — so agreement is
    evidence rather than tautology. Disagreement would mean a package labeled for a root
    type no model predicts, or predictions with no skeleton to correct them against.
    """
    matrix = rice_matrix_rows()
    assert matrix == {(2, 5): {"primary", "crown"}, (6, 10): {"crown"}}

    table = {}
    for row in load_skeleton_table():
        if row.species == "rice":
            table.setdefault(row.age_window, set()).add(row.root_type)
    assert table == matrix


@pytest.mark.parametrize(
    "age, expected",
    [
        (2, {"primary", "crown"}),
        (5, {"primary", "crown"}),
        (6, {"crown"}),
        (10, {"crown"}),
    ],
)
def test_rice_lookup_respects_the_age_window(age, expected):
    resolved = set()
    for root_type in ("primary", "crown"):
        try:
            lookup_skeleton("rice", root_type, age=age)
        except ValueError:
            continue
        resolved.add(root_type)
    assert resolved == expected


def test_an_age_split_species_requires_an_age():
    """Silently picking the first window would label old rice against a young skeleton."""
    with pytest.raises(ValueError, match="an age is required"):
        lookup_skeleton("rice", "crown")


def test_an_age_outside_every_window_fails_with_the_windows_listed():
    with pytest.raises(ValueError, match="14"):
        lookup_skeleton("rice", "crown", age=14)


def test_an_age_agnostic_row_ignores_the_age():
    """Only rice splits, so passing an age elsewhere must not narrow anything."""
    assert lookup_skeleton("soybean", "primary", age=99).node_count == 6


# --------------------------------------------------------------------------------------
# Loader validation — row-numbered, mirroring the selection matrix's loader
# --------------------------------------------------------------------------------------


def test_an_empty_table_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="no `skeletons:` rows"):
        load_skeleton_table(write_table(tmp_path, "skeletons: []\n"))


def test_a_missing_key_is_reported_with_its_row_number(tmp_path):
    body = (
        "skeletons:\n  - species: soybean\n    root_type: primary\n    mode: cylinder\n"
    )
    with pytest.raises(ValueError, match="row 0: missing required key 'node_count'"):
        load_skeleton_table(write_table(tmp_path, body))


def test_an_unknown_species_is_reported_with_its_row_number(tmp_path):
    body = "skeletons:\n  - species: wheat\n    root_type: primary\n    mode: cylinder\n    node_count: 6\n"
    with pytest.raises(ValueError, match="row 0: unknown species 'wheat'"):
        load_skeleton_table(write_table(tmp_path, body))


def test_an_unknown_root_type_is_reported_with_its_row_number(tmp_path):
    body = (
        "skeletons:\n"
        "  - species: soybean\n    root_type: primary\n    mode: cylinder\n    node_count: 6\n"
        "  - species: soybean\n    root_type: taproot\n    mode: cylinder\n    node_count: 6\n"
    )
    with pytest.raises(ValueError, match="row 1: unknown root_type 'taproot'"):
        load_skeleton_table(write_table(tmp_path, body))


@pytest.mark.parametrize("node_count", ["six", 1, 0, -3])
def test_a_node_count_that_cannot_describe_a_root_is_rejected(tmp_path, node_count):
    """Fewer than two nodes leaves no edge to label along."""
    body = (
        f"skeletons:\n  - species: soybean\n    root_type: primary\n    mode: cylinder\n"
        f"    node_count: {node_count}\n"
    )
    with pytest.raises(ValueError, match="node_count"):
        load_skeleton_table(write_table(tmp_path, body))


def test_a_gapped_age_window_is_rejected(tmp_path):
    """Same rule the selection matrix applies, so the two files cannot drift on it."""
    body = (
        "skeletons:\n  - species: rice\n    root_type: crown\n    mode: cylinder\n"
        '    age: "2, 3, 5"\n    node_count: 6\n'
    )
    with pytest.raises(ValueError, match="not contiguous"):
        load_skeleton_table(write_table(tmp_path, body))


def test_a_duplicate_entry_is_rejected(tmp_path):
    """A silent first-match win is how a table grows two answers to one question."""
    body = (
        "skeletons:\n"
        "  - species: soybean\n    root_type: primary\n    mode: cylinder\n    node_count: 6\n"
        "  - species: soybean\n    root_type: primary\n    mode: cylinder\n    node_count: 8\n"
    )
    with pytest.raises(ValueError, match="row 1: duplicate entry") as excinfo:
        load_skeleton_table(write_table(tmp_path, body))

    # Both rows are cylinder, so the message has to say which mode the clash is in.
    assert "cylinder" in str(excinfo.value)


# --------------------------------------------------------------------------------------
# add-skeleton-mode — Skeleton Table Mode Key
# --------------------------------------------------------------------------------------


def test_a_row_without_a_mode_is_rejected(tmp_path):
    """A default mode would be picking; a missing one is a table error, row-numbered."""
    body = (
        "skeletons:\n"
        "  - species: soybean\n    root_type: primary\n    mode: cylinder\n"
        "    node_count: 6\n"
        "  - species: soybean\n    root_type: lateral\n    node_count: 4\n"
    )
    with pytest.raises(ValueError, match="row 1: missing required key 'mode'"):
        load_skeleton_table(write_table(tmp_path, body))


def test_an_unknown_mode_lists_the_vocabulary(tmp_path):
    """``plates`` is the path token, not the contract's ``plate``."""
    body = (
        "skeletons:\n  - species: soybean\n    root_type: primary\n"
        "    mode: plates\n    node_count: 6\n"
    )
    with pytest.raises(ValueError, match="row 0: unknown mode 'plates'") as excinfo:
        load_skeleton_table(write_table(tmp_path, body))

    # Derived from the vocabulary, so a contract that grows a mode updates the check.
    for mode in sorted(MODE_VOCAB):
        assert mode in str(excinfo.value)


def test_multiplant_cylinder_is_a_valid_table_mode(tmp_path):
    """Characterisation: validation is vocabulary-driven, so every contract mode loads."""
    body = (
        "skeletons:\n  - species: arabidopsis\n    root_type: primary\n"
        "    mode: multiplant cylinder\n    node_count: 6\n"
    )
    assert load_skeleton_table(write_table(tmp_path, body))


def test_one_key_in_two_modes_is_not_a_duplicate(tmp_path):
    """RED against the mode-blind key: this was rejected as a duplicate."""
    body = (
        "skeletons:\n"
        "  - species: soybean\n    root_type: primary\n    mode: cylinder\n"
        "    age: null\n    node_count: 6\n"
        "  - species: soybean\n    root_type: primary\n    mode: plate\n"
        "    age: null\n    node_count: 8\n"
    )
    rows = load_skeleton_table(write_table(tmp_path, body))

    assert sorted((row.mode, row.node_count) for row in rows) == [
        ("cylinder", 6),
        ("plate", 8),
    ]


def test_a_pair_may_be_agnostic_in_one_mode_and_split_in_another(tmp_path):
    """RED against the mode-blind shadow check, which rejected this outright.

    It is the committed table's own shape: arabidopsis primary is age-agnostic in
    cylinder and split by age in plate. The shadow rule is about one lookup reaching
    every row, and rows in different modes are never candidates for the same lookup.
    """
    body = (
        "skeletons:\n"
        "  - species: arabidopsis\n    root_type: primary\n    mode: cylinder\n"
        "    age: null\n    node_count: 6\n"
        "  - species: arabidopsis\n    root_type: primary\n    mode: plate\n"
        '    age: "2, 3, 4, 5, 6, 7"\n    node_count: 8\n'
    )
    rows = load_skeleton_table(write_table(tmp_path, body))

    assert len(rows) == 2


def test_an_equivalently_spelled_age_window_is_a_duplicate(tmp_path):
    """RED: the dedup compared age *strings*, so ``"2,3"`` and ``"2, 3"`` both loaded."""
    body = (
        "skeletons:\n"
        "  - species: rice\n    root_type: crown\n    mode: cylinder\n"
        '    age: "2,3"\n    node_count: 6\n'
        "  - species: rice\n    root_type: crown\n    mode: cylinder\n"
        '    age: "2, 3"\n    node_count: 9\n'
    )
    with pytest.raises(ValueError, match="row 1"):
        load_skeleton_table(write_table(tmp_path, body))


def test_overlapping_age_windows_in_one_mode_are_rejected(tmp_path):
    """RED: overlapping windows loaded, and a lookup inside the overlap took the first.

    That is the silent first-match failure the dedup exists to prevent. Arabidopsis
    plate is now split by age, so a second plate window is the likely next edit.
    """
    body = (
        "skeletons:\n"
        "  - species: arabidopsis\n    root_type: primary\n    mode: plate\n"
        '    age: "2, 3, 4, 5, 6, 7"\n    node_count: 8\n'
        "  - species: arabidopsis\n    root_type: primary\n    mode: plate\n"
        '    age: "7, 8, 9"\n    node_count: 7\n'
    )
    with pytest.raises(ValueError, match="overlap") as excinfo:
        load_skeleton_table(write_table(tmp_path, body))

    assert "plate" in str(excinfo.value)


def test_the_same_window_in_two_modes_does_not_overlap(tmp_path):
    """Characterisation: overlap is per mode, like the rest of the key."""
    body = (
        "skeletons:\n"
        "  - species: rice\n    root_type: crown\n    mode: cylinder\n"
        '    age: "2, 3"\n    node_count: 6\n'
        "  - species: rice\n    root_type: crown\n    mode: plate\n"
        '    age: "2, 3"\n    node_count: 8\n'
    )
    assert len(load_skeleton_table(write_table(tmp_path, body))) == 2


def test_a_non_string_mode_is_reported_with_its_row_number(tmp_path):
    """RED: ``mode: [plate]`` raised ``TypeError: unhashable type`` with no row."""
    body = (
        "skeletons:\n  - species: soybean\n    root_type: primary\n"
        "    mode: [plate]\n    node_count: 6\n"
    )
    with pytest.raises(ValueError, match="row 0: unknown mode"):
        load_skeleton_table(write_table(tmp_path, body))


# --------------------------------------------------------------------------------------
# add-skeleton-mode — Mode-Aware Skeleton Lookup
# --------------------------------------------------------------------------------------


def two_mode_table(tmp_path):
    """Arabidopsis primary in both modes, shaped like the committed table; soybean in one.

    Built per test rather than at module scope, so a RED run fails test by test instead
    of breaking collection of the whole module.
    """
    body = (
        "skeletons:\n"
        "  - species: arabidopsis\n    root_type: primary\n    mode: cylinder\n"
        "    age: null\n    node_count: 6\n"
        "  - species: arabidopsis\n    root_type: primary\n    mode: plate\n"
        '    age: "2, 3, 4, 5, 6, 7"\n    node_count: 8\n    verified: true\n'
        "  - species: soybean\n    root_type: primary\n    mode: cylinder\n"
        "    age: null\n    node_count: 6\n    verified: true\n"
    )
    return load_skeleton_table(write_table(tmp_path, body))


@pytest.mark.parametrize("age", [None, 3, 9])
def test_an_omitted_mode_is_ambiguous_with_or_without_an_age(tmp_path, age):
    """RED: the mode-blind lookup returned the cylinder row for a plate caller.

    ``age=3`` falls inside the plate window and ``age=9`` outside it; neither may break
    the tie, because a lookup that consulted the age first would hand a plate caller the
    cylinder skeleton whenever the plate window missed.
    """
    table = two_mode_table(tmp_path)

    with pytest.raises(ValueError, match=r"cylinder.*plate") as excinfo:
        lookup_skeleton("arabidopsis", "primary", age=age, table=table)

    assert "mode=" in str(excinfo.value)


def test_an_omitted_mode_with_one_mode_is_unchanged(tmp_path):
    """Characterisation: a single-mode pair needs no mode, exactly as before."""
    table = two_mode_table(tmp_path)

    assert lookup_skeleton("soybean", "primary", table=table).node_count == 6


def test_a_given_mode_selects_its_own_row(tmp_path):
    table = two_mode_table(tmp_path)

    plate = lookup_skeleton("arabidopsis", "primary", age=3, mode="plate", table=table)
    cylinder = lookup_skeleton("arabidopsis", "primary", mode="cylinder", table=table)

    assert (plate.mode, plate.node_count) == ("plate", 8)
    assert (cylinder.mode, cylinder.node_count) == ("cylinder", 6)


def test_a_given_mode_with_no_row_names_the_existing_modes(tmp_path):
    """Soybean has no multiplant-cylinder row, and taking the cylinder one is picking."""
    table = two_mode_table(tmp_path)

    with pytest.raises(ValueError, match="multiplant cylinder") as excinfo:
        lookup_skeleton("soybean", "primary", mode="multiplant cylinder", table=table)

    assert "'cylinder'" in str(excinfo.value)


def test_a_given_mode_for_an_uncovered_pair_fails_as_before(tmp_path):
    """No row in any mode is the existing error, not "the modes that exist: []"."""
    table = two_mode_table(tmp_path)

    with pytest.raises(ValueError, match="No labeling skeleton is defined"):
        lookup_skeleton("pennycress", "primary", mode="plate", table=table)


def test_an_age_split_mode_without_an_age_lists_only_that_modes_windows(tmp_path):
    """The cylinder row is age-agnostic; it must not leak into the plate age error."""
    table = two_mode_table(tmp_path)

    with pytest.raises(ValueError, match="an age is required") as excinfo:
        lookup_skeleton("arabidopsis", "primary", mode="plate", table=table)
    assert "2-7 DAG" in str(excinfo.value)
    assert "plate" in str(excinfo.value)

    with pytest.raises(ValueError, match="2-7 DAG") as excinfo:
        lookup_skeleton("arabidopsis", "primary", age=8, mode="plate", table=table)
    assert "cylinder" not in str(excinfo.value)


def test_a_mode_outside_the_vocabulary_is_reported_as_unknown(tmp_path):
    """RED: a misspelled mode was told to "add a row for this mode" — one the loader rejects."""
    table = two_mode_table(tmp_path)

    with pytest.raises(ValueError, match="unknown mode 'Plate'") as excinfo:
        lookup_skeleton("arabidopsis", "primary", age=3, mode="Plate", table=table)

    assert "add a row" not in str(excinfo.value)
    for mode in sorted(MODE_VOCAB):
        assert mode in str(excinfo.value)


def test_the_committed_plate_row_requires_an_age():
    """Scenario: An age-split mode requires an age, on the committed table itself."""
    with pytest.raises(ValueError, match="an age is required") as excinfo:
        lookup_skeleton("arabidopsis", "primary", mode="plate")

    assert "2-7 DAG" in str(excinfo.value)


def test_the_warning_does_not_call_a_row_read_from_files_transcribed(caplog):
    """RED: every unverified row was called TRANSCRIBED, including the plate one."""
    with caplog.at_level("WARNING"):
        lookup_skeleton("arabidopsis", "primary", age=3, mode="plate")

    assert "NOT VERIFIED" in caplog.text
    assert "TRANSCRIBED" not in caplog.text


def test_the_unverified_warning_names_the_mode(caplog):
    """Once one pair has two modes, "(canola, lateral)" no longer says which skeleton."""
    with caplog.at_level("WARNING"):
        lookup_skeleton("canola", "lateral")

    assert "NOT VERIFIED" in caplog.text
    assert "cylinder" in caplog.text


# --------------------------------------------------------------------------------------
# Blocking review of #40 — a row that loads but can never be reached, and `verified`
# --------------------------------------------------------------------------------------


def test_an_age_agnostic_row_may_not_shadow_an_age_split_one(tmp_path):
    """RED against the port: both loaded cleanly and the age-split row did nothing.

    The per-key dedup above does not catch this — the keys genuinely differ — but
    ``lookup_skeleton`` returns the age-agnostic row before it ever consults the age, so
    ``lookup("rice", "crown", age=7)`` answered with the agnostic row's count and the
    9-node age row was unreachable. That is the same silent-first-match failure the dedup
    exists to prevent, one level up.
    """
    body = (
        "skeletons:\n"
        "  - species: rice\n    root_type: crown\n    mode: cylinder\n    age: null\n    node_count: 6\n"
        "  - species: rice\n    root_type: crown\n    mode: cylinder\n"
        '    age: "6, 7, 8"\n    node_count: 9\n'
    )
    with pytest.raises(ValueError, match="both an age-agnostic row") as excinfo:
        load_skeleton_table(write_table(tmp_path, body))

    # The rule now applies per mode, so the message names the mode it fired in.
    assert "cylinder" in str(excinfo.value)


def test_a_fully_age_split_pair_is_still_allowed(tmp_path):
    """The positive control: rice's real split has no agnostic row and must keep loading."""
    rows = load_skeleton_table()
    rice_crown = [r for r in rows if (r.species, r.root_type) == ("rice", "crown")]

    assert len(rice_crown) == 2
    assert all(row.age is not None for row in rice_crown)


def test_the_table_records_which_rows_are_verified():
    """The header always said so in prose; nothing downstream could read it."""
    # Keyed on the mode too: keyed on (species, root_type) alone, the last row per pair
    # wins, and a second-mode row silently replaces the one being asserted about.
    rows = {(r.species, r.mode, r.root_type): r for r in load_skeleton_table()}

    # Verified 2026-08-04 against the real WEEP artifacts that became the published
    # collection.
    assert rows[("soybean", "cylinder", "primary")].verified
    assert rows[("soybean", "cylinder", "lateral")].verified
    # Transcribed from the advisory doc table and not yet confirmed against an artifact.
    assert not rows[("canola", "cylinder", "lateral")].verified
    assert not rows[("arabidopsis", "cylinder", "primary")].verified


def test_looking_up_an_unverified_skeleton_warns(caplog):
    with caplog.at_level("WARNING"):
        lookup_skeleton("canola", "lateral")

    assert "NOT VERIFIED" in caplog.text
    assert "canola" in caplog.text


def test_looking_up_a_verified_skeleton_is_quiet(caplog):
    with caplog.at_level("WARNING"):
        lookup_skeleton("soybean", "primary")

    assert "NOT VERIFIED" not in caplog.text


# `yes` is deliberately absent: YAML parses it as a boolean, so it is a legitimate value.
@pytest.mark.parametrize("bad", ["maybe", "1", "null"])
def test_a_non_boolean_verified_flag_is_rejected(tmp_path, bad):
    body = (
        "skeletons:\n  - species: soybean\n    root_type: primary\n    mode: cylinder\n"
        f"    node_count: 6\n    verified: {bad}\n"
    )
    with pytest.raises(ValueError, match="verified must be true or false"):
        load_skeleton_table(write_table(tmp_path, body))


@pytest.mark.parametrize(
    "body,expected",
    [
        ("- a\n- b\n", "expected a mapping"),
        ("skeletons: 5\n", "expected a list of rows"),
        ("skeletons:\n  - just a string\n", "expected a mapping of keys"),
    ],
)
def test_a_malformed_table_fails_as_a_message_not_an_attribute_error(
    tmp_path, body, expected
):
    # `AttributeError` is not in the CLI's catch, so these used to reach the operator as
    # tracebacks.
    with pytest.raises(ValueError, match=expected):
        load_skeleton_table(write_table(tmp_path, body))


# --------------------------------------------------------------------------------------
# Task 6.5 — verification against the published collections
# --------------------------------------------------------------------------------------


# The per-collection resolution the integration test below runs, unit-tested here with fake
# collections so the #61 fix — the registry is queried for `dataset` collections, and each
# collection is looked up in its own mode — is verified in CI, where the download is not.


class _FakeCollection:
    def __init__(self, name):
        self.name = name


class _FakeApi:
    """Records the artifact type it is queried with; returns the given collections."""

    def __init__(self, names=()):
        self.names = names
        self.queried = []

    def artifact_collections(self, project, type_name):
        self.queried.append((project, type_name))
        return [_FakeCollection(name) for name in self.names]


def test_the_registry_is_queried_for_dataset_collections():
    """RED against #61: the test asked for ``model``, which the labels registry rejects."""
    api = _FakeApi()
    assert list(_label_collections(api, "entity-org/labels")) == []
    assert api.queried == [("entity-org/labels", "dataset")]


def test_a_mapped_collection_is_checked_in_its_own_mode_and_age():
    """The plate collection is age-split, so the map carries an age as well as a mode."""
    mismatch = _check_skeleton(
        "plate_arabidopsis_2-7DAG_primary_8nodes_labels",
        "arabidopsis_primary",
        tuple(f"r{i}" for i in range(1, 9)),
    )
    assert mismatch is None


def test_an_unmapped_two_mode_collection_is_reported_not_guessed():
    mismatch = _check_skeleton(
        "arabidopsis_somewhere_labels",
        "arabidopsis_primary",
        tuple(f"r{i}" for i in range(1, 7)),
    )
    assert mismatch is not None
    assert "more than one capture mode" in mismatch


def test_a_node_count_disagreement_names_the_collection_and_both_counts():
    mismatch = _check_skeleton(
        "cyl_arabidopsis_7-11DAG_primary_6nodes_labels",
        "arabidopsis_primary",
        tuple(f"r{i}" for i in range(1, 8)),
    )
    assert mismatch.startswith("cyl_arabidopsis_7-11DAG_primary_6nodes_labels:")
    assert "7 nodes" in mismatch and "table says 6" in mismatch


def test_an_auto_generated_skeleton_name_is_reported_as_a_mismatch():
    """Plate files name their skeleton ``Skeleton-N``; that is reported, not skipped."""
    mismatch = _check_skeleton(
        "plate_arabidopsis_2-7DAG_primary_8nodes_labels",
        "Skeleton-1",
        tuple(f"r{i}" for i in range(1, 9)),
    )
    assert mismatch is not None
    assert "Skeleton-1" in mismatch


#: Opt-in for the registry verification below. It is marked ``integration`` (so CI's
#: ``-m "not integration"`` deselects it) *and* gated on this variable, because unlike the
#: other integration tests it downloads 170 MB - 1.2 GB per collection, eight times. A
#: local run should not do that by accident.
_REGISTRY_CHECK_ENV = "SLEAP_ROOTS_LABEL_SKELETON_CHECK"

#: The mode (and, for an age-split row, an age inside its window) each collection is
#: checked in. An explicit literal, not parsed from names: only these two collections'
#: names carry a mode, and a collection absent from the map is looked up with no mode, so
#: a species and root type with rows in several modes is *reported* rather than guessed.
_COLLECTION_MODES: dict[str, tuple[Optional[str], Optional[int]]] = {
    "plate_arabidopsis_2-7DAG_primary_8nodes_labels": ("plate", 2),
    "cyl_arabidopsis_7-11DAG_primary_6nodes_labels": ("cylinder", None),
}


def _label_collections(api, project):
    """Yield the labels registry's collections.

    The labels registry holds ``dataset`` collections; querying ``model`` raises
    ``Unable to parse 'ArtifactCollections' response data`` (#61, measured in #58). The
    type is the inventory's own constant, so the two checks cannot drift apart again.
    """
    from sleap_roots_training.inventory.verify import _LABELS_ARTIFACT_TYPE

    return api.artifact_collections(project, _LABELS_ARTIFACT_TYPE)


def _check_skeleton(collection_name, skeleton_name, node_names):
    """Return a mismatch line for one skeleton in one collection, or ``None`` if it agrees.

    ``Skeleton-N`` names — every plate file's — do not partition into a species and root
    type, so they are reported here rather than skipped: a check that skipped them would
    pass without having looked.
    """
    species, _, root_type = skeleton_name.partition("_")
    mode, age = _COLLECTION_MODES.get(collection_name, (None, None))
    try:
        row = lookup_skeleton(species, root_type, age=age, mode=mode)
    except ValueError as error:
        return f"{collection_name}: {skeleton_name}: {error}"
    if tuple(node_names) != row.node_names:
        # An unmapped collection resolved only because the pair has one mode; say so,
        # so a disagreement is not read as a mode-verified one.
        assumed = (
            f" (mode unknown; checked against the table's only mode {row.mode!r})"
            if mode is None
            else ""
        )
        return (
            f"{collection_name}: {skeleton_name} has {len(node_names)} nodes "
            f"{list(node_names)}, table says {row.node_count} {list(row.node_names)}"
            f"{assumed}"
        )
    return None


@pytest.mark.integration
def test_the_table_agrees_with_the_published_label_collections(tmp_path):
    """Read every collection in ``wandb-registry-sleap-roots-labels`` and diff node counts.

    This is what converts the table from hypothesis to record (design.md Decision 7), and
    it is the same check ``#10``'s ``LabelCard.node_count`` will run against the contract's
    skeleton-coherence rule. Run it deliberately::

        SLEAP_ROOTS_LABEL_SKELETON_CHECK=1 uv run pytest -m integration \\
            tests/test_labeling_skeletons.py

    A disagreement is a finding either way — the table may be wrong, or a published
    collection may have been labeled against a skeleton nobody recorded — so it reports
    every mismatch rather than stopping at the first, and names the collection. Run on
    2026-09-24, it reported all eight collections: every published skeleton is named
    ``Skeleton-N``, which does not partition into a species and root type (#64). Their
    node counts, read by hand, agree with every row. Until the check can learn each
    collection's key, it cannot flip a row to ``verified: true``.
    """
    if not os.environ.get(_REGISTRY_CHECK_ENV):
        pytest.skip(
            f"set {_REGISTRY_CHECK_ENV}=1 to download and check the collections"
        )
    wandb = pytest.importorskip("wandb")
    import pathlib

    import sleap_io as sio

    from sleap_roots_training.registry.config import resolve_registry_config

    # Same entity/org resolution the model registry uses, pointed at the labels registry.
    cfg = resolve_registry_config()
    project = f"{cfg.entity}-org/wandb-registry-sleap-roots-labels"
    api = wandb.Api()

    mismatches: list[str] = []
    checked = 0
    for collection in _label_collections(api, project):
        artifact = api.artifact(f"{project}/{collection.name}:latest")
        directory = artifact.download(root=str(tmp_path / collection.name))
        for slp in sorted(pathlib.Path(directory).rglob("*.slp")):
            labels = sio.load_slp(str(slp), open_videos=False)
            for skeleton in labels.skeletons:
                checked += 1
                names = tuple(node.name for node in skeleton.nodes)
                mismatch = _check_skeleton(collection.name, skeleton.name, names)
                if mismatch:
                    mismatches.append(mismatch)

    assert checked, "no skeletons were read; the registry query found nothing"
    assert not mismatches, "\n".join(mismatches)


# --------------------------------------------------------------------------------------
# Blocking review of #40, second pass — the table is parsed once, not once per lookup
# --------------------------------------------------------------------------------------


def test_the_table_is_parsed_once_across_repeated_lookups(monkeypatch):
    """Measured at ~6.5 ms a call, and `skeleton_for` calls it once per age.

    The builder and the orchestrator each resolve skeletons, so a 10-age two-root-type
    build re-read and re-validated the same committed file about forty times — roughly a
    quarter of a second spent parsing something that cannot change mid-build.
    """
    from sleap_roots_training.labeling import skeletons as sk

    sk._parse_table_cached.cache_clear()
    parses = []
    real_parse = sk._parse_table
    monkeypatch.setattr(
        sk, "_parse_table", lambda path: (parses.append(path), real_parse(path))[1]
    )

    for _ in range(10):
        lookup_skeleton("soybean", "primary")

    assert len(parses) == 1, f"parsed {len(parses)} times, expected once"


def test_an_edited_table_is_re_read_rather_than_served_from_the_cache(tmp_path):
    """Keying the cache on the path alone would make an in-place edit invisible.

    That is a footgun aimed squarely at the operator correcting a node count — which the
    table's own header says is expected for the three TRANSCRIBED, NOT VERIFIED crops — so
    the key is the file's *content* hash. Size and mtime were tried and rejected: a
    same-length correction (``6`` to ``9``) leaves the size identical, and a checkout can
    reuse an mtime at coarser resolution than an edit-and-rerun takes.
    """
    body = "skeletons:\n  - species: soybean\n    root_type: primary\n    mode: cylinder\n    node_count: 6\n"
    path = write_table(tmp_path, body)
    assert load_skeleton_table(path)[0].node_count == 6

    # Corrected in place, at the same path.
    path.write_text(body.replace("node_count: 6", "node_count: 8"), encoding="utf-8")

    assert load_skeleton_table(path)[0].node_count == 8


def test_the_cached_rows_cannot_be_mutated_by_a_caller():
    """A shared cached value is only safe if nobody can write through it."""
    rows = load_skeleton_table()

    assert isinstance(rows, tuple)
    with pytest.raises(Exception):
        rows[0].node_count = 99
