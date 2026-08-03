"""Characterization tests for labeling frame selection.

Decision 1 sequences the port: these pin the behavior the port inherited from the vault
script *before* anything changes, so a later "did the port break something?" question has
a commit to point at. Behavior changes are section 2's later tasks and land separately.

Two tests are `xfail` — they document defects in the *original* that the characterization
pass surfaced (design.md F9, F10), not port errors. They are strict, so whichever task
fixes them has to remove the marker rather than silently absorbing the change.
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
    (6, "B2", 1, 0, "images/Wave1/Day3_20250101/B2/1.jpg", "WEEP-1-4_B2_age3_0.jpg"),
    (6, "B2", 37, 1, "images/Wave1/Day3_20250101/B2/37.jpg", "WEEP-1-4_B2_age3_1.jpg"),
    (10, "C2", 1, 0, "images/Wave1/Day5_20250103/C2/1.jpg", "A3244_C2_age5_0.jpg"),
    (10, "C2", 37, 1, "images/Wave1/Day5_20250103/C2/37.jpg", "A3244_C2_age5_1.jpg"),
    (14, "D2", 1, 0, "images/Wave1/Day5_20250103/D2/1.jpg", "WEEP-1-4_D2_age5_0.jpg"),
    (14, "D2", 37, 1, "images/Wave1/Day5_20250103/D2/37.jpg", "WEEP-1-4_D2_age5_1.jpg"),
]


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
# The sampling pool and the stratification over it
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


# --------------------------------------------------------------------------------------
# The frames selected, their order, and the manifest rows produced
# --------------------------------------------------------------------------------------


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


def test_view_indices_are_evenly_spaced_over_the_rotation():
    # The vault script's formula: `step = total_views // views_per_plant`, taken from
    # index 1. Pinned as the port's starting point; note it is not nested — [1, 25, 49]
    # is not a subset of [1, 19, 37, 55], which is what task 2.6 will demonstrate.
    assert ss.select_view_indices(3) == [1, 25, 49]
    assert ss.select_view_indices(4) == [1, 19, 37, 55]
    assert ss.select_view_indices(6) == [1, 13, 25, 37, 49, 61]


def test_manifest_carries_every_required_column_in_order(tmp_path):
    manifest = run_selection(tmp_path)
    assert list(manifest.columns) == list(ss.MANIFEST_COLUMNS)


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


def test_frame_index_is_a_per_scan_counter(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=2, views_per_plant=4)
    for scan_id, group in manifest.groupby("scan_id"):
        assert list(group["frame_index"]) == list(range(len(group))), scan_id


# --------------------------------------------------------------------------------------
# Loading the QC-cleaned pool
# --------------------------------------------------------------------------------------


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


@pytest.mark.xfail(
    strict=True,
    reason="F9: `parent.glob(name)` only matches a wildcard in the filename, so the "
    "per-age-group directory layout QC actually writes never resolves — even though the "
    "branch's own logging (`f.parent.name`) assumes exactly that layout. The workflow "
    "doc hides it by concatenating the files by hand in Phase 1.",
)
def test_glob_resolves_a_wildcard_in_a_directory_component(tmp_path):
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


# --------------------------------------------------------------------------------------
# Task 2.4 — determinism (expected GREEN against the port, per F3)
# --------------------------------------------------------------------------------------


def test_selection_is_deterministic_across_runs(tmp_path):
    first = run_selection(tmp_path, out_name="a.csv")
    second = run_selection(tmp_path, out_name="b.csv")
    pd.testing.assert_frame_equal(first, second)


@pytest.mark.xfail(
    strict=True,
    reason="F10: `.sample(random_state=seed)` draws by position within the group, so the "
    "same scans in a different row order select different plants. `scans.csv` is a Bloom "
    "export that Decision 6's recovery path re-fetches, so a reordering re-download "
    "silently changes the label set. Task 2.7's stable ordering closes it.",
)
def test_selection_is_deterministic_across_row_order_of_scans_csv(tmp_path):
    ordered = run_selection(tmp_path, out_name="a.csv")
    shuffled = run_selection(
        tmp_path,
        out_name="b.csv",
        scans_csv=write_scans(tmp_path / "alt", rows=list(reversed(SCAN_ROWS))),
    )
    assert sorted(ordered["output_filename"]) == sorted(shuffled["output_filename"])
