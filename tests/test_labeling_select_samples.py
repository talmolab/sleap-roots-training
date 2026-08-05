"""Characterization + deviation tests for labeling frame selection.

Sequenced per design.md Decision 1: the ``characterization`` tests pin the behavior the
port inherited from the vault script, and the ``deviation`` tests pin the changes this
change makes on purpose (tasks 2.5, 2.7, 2.9, 2.10). Each deviation test names the legacy
behavior it replaced, so the port's starting point stays readable after the change lands.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from sleap_roots_training.labeling import select_samples as ss

# Two ages x two accessions x four plants, one scan per plant, plus one plant that QC
# drops. Small enough to pin row-by-row, wide enough that stratification has a choice to
# make in every group.
SCAN_ROWS = [
    # scan_id, plant_qr_code, plant_age_days, accession_id, wave_number, scan_path
    (1, "A1", 3, 100, 1, "images/Wave1/Day3_20250101/A1"),
    (2, "A2", 3, 100, 1, "images/Wave1/Day3_20250101/A2"),
    (3, "A3", 3, 100, 1, "images/Wave1/Day3_20250101/A3"),
    (4, "A4", 3, 100, 1, "images/Wave1/Day3_20250101/A4"),
    (5, "B1", 3, 200, 1, "images/Wave1/Day3_20250101/B1"),
    (6, "B2", 3, 200, 1, "images/Wave1/Day3_20250101/B2"),
    (7, "B3", 3, 200, 1, "images/Wave1/Day3_20250101/B3"),
    (8, "B4", 3, 200, 1, "images/Wave1/Day3_20250101/B4"),
    (9, "C1", 5, 100, 1, "images/Wave1/Day5_20250103/C1"),
    (10, "C2", 5, 100, 1, "images/Wave1/Day5_20250103/C2"),
    (11, "C3", 5, 100, 1, "images/Wave1/Day5_20250103/C3"),
    (12, "C4", 5, 100, 1, "images/Wave1/Day5_20250103/C4"),
    (13, "D1", 5, 200, 1, "images/Wave1/Day5_20250103/D1"),
    (14, "D2", 5, 200, 1, "images/Wave1/Day5_20250103/D2"),
    (15, "D3", 5, 200, 1, "images/Wave1/Day5_20250103/D3"),
    (16, "D4", 5, 200, 1, "images/Wave1/Day5_20250103/D4"),
    # Poorly germinated — present in scans.csv, absent from the QC-cleaned pool.
    (17, "Z9", 3, 100, 1, "images/Wave1/Day3_20250101/Z9"),
]

CLEAN_BARCODES = [r[1] for r in SCAN_ROWS if r[1] != "Z9"]

ACCESSION_NAMES = {100: "A3244", 200: "WEEP-1-4"}

#: The exact selection for ``plants_per_group=1, views_per_plant=2`` over the fixture:
#: (scan_id, plant_qr_code, view_index, frame_index, source_image, output_filename).
#: One plant per age x accession group, two views each, rows in ``scans.csv`` order.
EXPECTED_ROWS = [
    (2, "A2", 1, 0, "images/Wave1/Day3_20250101/A2/1.jpg", "A3244_A2_age3_0.jpg"),
    (2, "A2", 37, 1, "images/Wave1/Day3_20250101/A2/37.jpg", "A3244_A2_age3_1.jpg"),
    (7, "B3", 1, 0, "images/Wave1/Day3_20250101/B3/1.jpg", "WEEP-1-4_B3_age3_0.jpg"),
    (7, "B3", 37, 1, "images/Wave1/Day3_20250101/B3/37.jpg", "WEEP-1-4_B3_age3_1.jpg"),
    (9, "C1", 1, 0, "images/Wave1/Day5_20250103/C1/1.jpg", "A3244_C1_age5_0.jpg"),
    (9, "C1", 37, 1, "images/Wave1/Day5_20250103/C1/37.jpg", "A3244_C1_age5_1.jpg"),
    (14, "D2", 1, 0, "images/Wave1/Day5_20250103/D2/1.jpg", "WEEP-1-4_D2_age5_0.jpg"),
    (14, "D2", 37, 1, "images/Wave1/Day5_20250103/D2/37.jpg", "WEEP-1-4_D2_age5_1.jpg"),
]

#: A scan that repeats an existing plant's ``(plant_qr_code, plant_age_days)`` pair under
#: a second ``scan_id`` — the F6 collision. Task 0.8 established this does not occur in
#: real data, so the fixture manufactures it to prove selection refuses it.
COLLIDING_SCAN = (18, "A2", 3, 100, 1, "images/Wave1/Day3_20250101/A2_rescan")


def write_scans(tmp_path: Path, rows=SCAN_ROWS) -> Path:
    """Write a Bloom-shaped ``scans.csv`` and return its path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "scans.csv"
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "scan_id",
                "plant_qr_code",
                "plant_age_days",
                "accession_id",
                "wave_number",
                "scan_path",
            ]
        )
        writer.writerows(rows)
    return path


def write_cleaned(tmp_path: Path, barcodes=CLEAN_BARCODES, column="Barcode") -> Path:
    """Write a QC-cleaned table and return its path."""
    path = tmp_path / "10_final_data.csv"
    pd.DataFrame({column: barcodes, "some_trait": range(len(barcodes))}).to_csv(
        path, index=False
    )
    return path


def run_selection(
    tmp_path: Path, out_name="sample_manifest.csv", **kwargs
) -> pd.DataFrame:
    """Run selection over the standard fixture, returning the manifest."""
    scans = kwargs.pop("scans_csv", None) or write_scans(tmp_path)
    cleaned = kwargs.pop("cleaned_csv", None) or write_cleaned(tmp_path)
    kwargs.setdefault("accession_names", ACCESSION_NAMES)
    kwargs.setdefault("plants_per_group", 2)
    return ss.select_samples(cleaned, scans, tmp_path / out_name, **kwargs)


# --------------------------------------------------------------------------------------
# Characterization — behavior the port inherited unchanged
# --------------------------------------------------------------------------------------


def test_qc_filter_excludes_plants_missing_from_the_cleaned_pool(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=99)
    assert "Z9" not in set(manifest["plant_qr_code"])
    assert set(manifest["plant_qr_code"]) == set(CLEAN_BARCODES)


def test_stratifies_n_plants_per_age_x_accession_group(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=2)
    per_group = manifest.groupby(["plant_age_days", "accession_id"])[
        "plant_qr_code"
    ].nunique()
    assert per_group.to_dict() == {(3, 100): 2, (3, 200): 2, (5, 100): 2, (5, 200): 2}


def test_group_smaller_than_the_request_is_taken_whole(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=99)
    per_group = manifest.groupby(["plant_age_days", "accession_id"])[
        "plant_qr_code"
    ].nunique()
    # Four clean plants in each group; asking for 99 must not raise or pad.
    assert per_group.to_dict() == {(3, 100): 4, (3, 200): 4, (5, 100): 4, (5, 200): 4}


def test_row_count_is_plants_times_views(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=2, views_per_plant=3)
    assert len(manifest) == 8 * 3


def test_manifest_row_content_and_order(tmp_path):
    """Pin the exact rows: which plants, which views, in which order."""
    manifest = run_selection(tmp_path, plants_per_group=1, views_per_plant=2)
    got = [
        (
            r.scan_id,
            r.plant_qr_code,
            r.view_index,
            r.frame_index,
            r.source_image,
            r.output_filename,
        )
        for r in manifest.itertuples()
    ]
    assert got == EXPECTED_ROWS


def test_manifest_is_written_to_disk_and_matches_the_return_value(tmp_path):
    manifest = run_selection(tmp_path)
    on_disk = pd.read_csv(tmp_path / "sample_manifest.csv")
    pd.testing.assert_frame_equal(on_disk, manifest.reset_index(drop=True))


def test_accession_name_falls_back_to_the_numeric_id(tmp_path):
    manifest = run_selection(tmp_path, accession_names=None, plants_per_group=1)
    assert set(manifest["accession_name"]) == {"100", "200"}
    assert all(
        name.startswith(("100_", "200_")) for name in manifest["output_filename"]
    )


def test_accession_name_is_used_in_the_filename_when_supplied(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=1)
    assert set(manifest["accession_name"]) == {"A3244", "WEEP-1-4"}
    row = manifest.iloc[0]
    assert row["output_filename"] == (
        f"{row['accession_name']}_{row['plant_qr_code']}"
        f"_age{row['plant_age_days']}_{row['frame_index']}.jpg"
    )


def test_source_image_is_the_scan_path_joined_with_the_view_filename(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=1)
    for row in manifest.itertuples():
        assert row.source_image == f"{row.source_scan_path}/{row.view_index}.jpg"


def test_barcode_column_falls_back_to_plant_qr_code(tmp_path):
    # The QC pipeline renames the column to `Barcode`; upstream of it, it is
    # `plant_qr_code`. Both must resolve.
    cleaned = write_cleaned(tmp_path, column="plant_qr_code")
    manifest = run_selection(tmp_path, cleaned_csv=cleaned, plants_per_group=99)
    assert set(manifest["plant_qr_code"]) == set(CLEAN_BARCODES)


def test_cleaned_csv_may_be_a_glob_over_per_age_group_files(tmp_path):
    group_dir = tmp_path / "qc"
    group_dir.mkdir()
    for age, barcodes in (("day3", CLEAN_BARCODES[:8]), ("day5", CLEAN_BARCODES[8:])):
        pd.DataFrame({"Barcode": barcodes}).to_csv(
            group_dir / f"{age}_final_data.csv", index=False
        )
    manifest = run_selection(
        tmp_path, cleaned_csv=group_dir / "*_final_data.csv", plants_per_group=99
    )
    assert set(manifest["plant_qr_code"]) == set(CLEAN_BARCODES)


def test_a_glob_matching_nothing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No files matching"):
        run_selection(tmp_path, cleaned_csv=tmp_path / "nope" / "*.csv")


# --------------------------------------------------------------------------------------
# Task 2.4 — determinism (expected GREEN against the port, per F3)
# --------------------------------------------------------------------------------------


def test_selection_is_deterministic_across_runs(tmp_path):
    first = run_selection(tmp_path, out_name="a.csv")
    second = run_selection(tmp_path, out_name="b.csv")
    pd.testing.assert_frame_equal(first, second)


def test_selection_is_deterministic_across_row_order_of_scans_csv(tmp_path):
    # Deviation (2.7): the vault script's `.sample()` drew from the group in row order,
    # so re-exporting `scans.csv` with the rows in a different order silently changed
    # which plants were labeled. Ordering by a stable key removes that coupling.
    ordered = run_selection(tmp_path, out_name="a.csv")
    shuffled = run_selection(
        tmp_path,
        out_name="b.csv",
        scans_csv=write_scans(tmp_path / "alt", rows=list(reversed(SCAN_ROWS))),
    )
    assert sorted(ordered["output_filename"]) == sorted(shuffled["output_filename"])


def test_a_different_seed_selects_a_different_set_of_plants(tmp_path):
    default = run_selection(tmp_path, out_name="a.csv", plants_per_group=1)
    reseeded = run_selection(tmp_path, out_name="b.csv", plants_per_group=1, seed=7)
    assert set(default["plant_qr_code"]) != set(reseeded["plant_qr_code"])


# --------------------------------------------------------------------------------------
# Task 2.6 / 2.7 — monotone widening (deliberate deviation; RED against the vault script)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "narrow,wide", [(1, 2), (2, 3), (3, 4), (1, 4), (4, 6), (6, 8)]
)
def test_widening_views_yields_a_superset(narrow, wide):
    assert set(ss.select_view_indices(narrow)) <= set(ss.select_view_indices(wide))


def test_view_indices_are_nested_across_every_count(tmp_path):
    previous: set[int] = set()
    for count in range(1, ss.TOTAL_VIEWS + 1):
        current = set(ss.select_view_indices(count))
        assert previous <= current, f"{count} views is not a superset of {count - 1}"
        assert len(current) == count
        previous = current


def test_view_indices_deviate_from_the_vault_formula_only_where_it_was_not_monotone():
    # The vault script computed `step = 72 // views_per_plant` from index 1. Four views
    # are unchanged; three are not, and that is exactly the case where the old formula
    # broke nesting ([1, 25, 49] is not a subset of [1, 19, 37, 55]).
    assert ss.select_view_indices(4) == [1, 19, 37, 55]
    assert ss.select_view_indices(3) == [1, 19, 37]
    assert not set([1, 25, 49]) <= set([1, 19, 37, 55])


def test_view_indices_are_ascending_and_in_range():
    views = ss.select_view_indices(6)
    assert views == sorted(views)
    assert all(1 <= v <= ss.TOTAL_VIEWS for v in views)


def test_widening_plants_yields_a_superset(tmp_path):
    narrow = run_selection(tmp_path, out_name="a.csv", plants_per_group=1)
    wide = run_selection(tmp_path, out_name="b.csv", plants_per_group=3)
    assert set(narrow["plant_qr_code"]) <= set(wide["plant_qr_code"])


def test_widening_both_dimensions_yields_a_superset_of_frames(tmp_path):
    def frames(manifest):
        return set(zip(manifest["scan_id"], manifest["view_index"]))

    narrow = run_selection(
        tmp_path, out_name="a.csv", plants_per_group=1, views_per_plant=2
    )
    wide = run_selection(
        tmp_path, out_name="b.csv", plants_per_group=3, views_per_plant=4
    )
    assert frames(narrow) <= frames(wide)


# --------------------------------------------------------------------------------------
# Task 2.5 — `total_views` is a validated parameter, not a silent constant
# --------------------------------------------------------------------------------------


def test_total_views_defaults_to_the_bloom_cylinder_convention():
    assert ss.TOTAL_VIEWS == 72


def test_more_views_requested_than_exist_fails_loudly():
    with pytest.raises(ValueError, match=r"between 1 and total_views \(24\), got 30"):
        ss.select_view_indices(30, total_views=24)


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_view_count_fails_loudly(bad):
    with pytest.raises(ValueError, match="views_per_plant must be between"):
        ss.select_view_indices(bad)


def test_a_non_positive_total_views_fails_loudly():
    with pytest.raises(ValueError, match="total_views must be >= 1"):
        ss.select_view_indices(1, total_views=0)


def test_selection_honors_a_non_default_total_views(tmp_path):
    manifest = run_selection(
        tmp_path, plants_per_group=1, views_per_plant=2, total_views=24
    )
    assert sorted(set(manifest["view_index"])) == [1, 13]


def test_selection_rejects_a_view_count_larger_than_the_scan(tmp_path):
    with pytest.raises(ValueError, match=r"between 1 and total_views \(8\), got 9"):
        run_selection(tmp_path, views_per_plant=9, total_views=8)


# --------------------------------------------------------------------------------------
# Task 2.8 / 2.9 — manifest shape and curated-filename uniqueness
# --------------------------------------------------------------------------------------


def test_manifest_carries_every_required_column_in_order(tmp_path):
    manifest = run_selection(tmp_path)
    assert list(manifest.columns) == list(ss.MANIFEST_COLUMNS)


def test_manifest_columns_match_the_documented_package_contract(tmp_path):
    # Decision 3 enumerates these; #10's `publish-labels` builds a LabelCard from them.
    assert set(ss.MANIFEST_COLUMNS) == {
        "scan_id",
        "plant_qr_code",
        "plant_age_days",
        "accession_id",
        "accession_name",
        "wave_number",
        "view_index",
        "frame_index",
        "source_scan_path",
        "source_image",
        "output_filename",
    }


def test_manifest_has_exactly_one_row_per_selected_frame(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=2, views_per_plant=3)
    frames = set(zip(manifest["scan_id"], manifest["view_index"]))
    assert len(frames) == len(manifest) == 8 * 3


def test_no_required_field_is_empty(tmp_path):
    manifest = run_selection(tmp_path)
    assert not manifest.isna().to_numpy().any()


def test_output_filename_is_unique_across_the_manifest(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=99, views_per_plant=4)
    assert manifest["output_filename"].is_unique


def test_a_colliding_output_filename_fails_and_names_the_scans(tmp_path):
    # Two scan_ids sharing a (plant_qr_code, plant_age_days) pair: the frame counter is
    # keyed by scan_id but the filename is not, so both scans produce `..._age3_0.jpg`.
    scans = write_scans(tmp_path / "collide", rows=SCAN_ROWS + [COLLIDING_SCAN])
    with pytest.raises(ValueError, match="output_filename is not unique") as excinfo:
        run_selection(tmp_path, scans_csv=scans, plants_per_group=99)
    message = str(excinfo.value)
    assert "A3244_A2_age3_0.jpg" in message
    # The error must name the offending scans, since the fix is upstream in the record.
    assert "2" in message and "18" in message


def test_a_collision_writes_no_manifest(tmp_path):
    scans = write_scans(tmp_path / "collide", rows=SCAN_ROWS + [COLLIDING_SCAN])
    with pytest.raises(ValueError):
        run_selection(tmp_path, scans_csv=scans, plants_per_group=99)
    assert not (tmp_path / "sample_manifest.csv").exists()


# --------------------------------------------------------------------------------------
# Task 2.10 — `frame_index` is the authoritative position of a frame within its scan
# --------------------------------------------------------------------------------------


def test_frame_index_is_the_rank_of_the_view_within_its_scan(tmp_path):
    """Pin the one authoritative derivation of a frame's position.

    ``build_slp_project.py`` re-derives position by sorting on ``view_index`` and
    enumerating, never reading this column (design.md F6). The two agreed only because
    the vault script's views happened to be ascending. This pins ``frame_index`` as the
    single source of truth and proves the sort-and-enumerate derivation agrees with it,
    so section 4's builder can read the column instead of recomputing it.
    """
    manifest = run_selection(tmp_path, plants_per_group=2, views_per_plant=4)
    for scan_id, group in manifest.groupby("scan_id"):
        by_view = group.sort_values("view_index")
        assert list(by_view["frame_index"]) == list(range(len(by_view))), scan_id
        assert list(group["frame_index"]) == list(by_view["frame_index"]), scan_id


def test_windows_separators_in_scan_path_are_normalized_to_posix(tmp_path):
    # Deviation (7j): the manifest travels inside the package, so a path written on the
    # vault's Windows machine must still resolve on the machine that opens it.
    windows_rows = [(*row[:5], row[5].replace("/", "\\")) for row in SCAN_ROWS]
    manifest = run_selection(
        tmp_path,
        scans_csv=write_scans(tmp_path / "win", rows=windows_rows),
        plants_per_group=1,
    )
    assert not any("\\" in p for p in manifest["source_scan_path"])
    assert not any("\\" in p for p in manifest["source_image"])
    assert manifest.iloc[0]["source_scan_path"].startswith("images/Wave1/")


def test_frame_index_appears_in_the_output_filename(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=1, views_per_plant=3)
    for row in manifest.itertuples():
        assert row.output_filename.endswith(f"_{row.frame_index}.jpg")


# --------------------------------------------------------------------------------------
# Glob branch — generalized to the layout QC actually writes
# --------------------------------------------------------------------------------------


def test_glob_resolves_a_wildcard_in_a_directory_component(tmp_path):
    # The vault script globbed `parent.glob(name)`, so a wildcard directory never
    # resolved and the workflow doc concatenated the group files by hand first.
    group_dir = tmp_path / "qc"
    for age, barcodes in (("day3", CLEAN_BARCODES[:8]), ("day5", CLEAN_BARCODES[8:])):
        sub = group_dir / age
        sub.mkdir(parents=True)
        pd.DataFrame({"Barcode": barcodes}).to_csv(
            sub / "10_final_data.csv", index=False
        )
    manifest = run_selection(
        tmp_path,
        cleaned_csv=group_dir / "*" / "10_final_data.csv",
        plants_per_group=99,
    )
    assert set(manifest["plant_qr_code"]) == set(CLEAN_BARCODES)
