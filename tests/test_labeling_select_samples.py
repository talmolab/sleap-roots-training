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
    (2, "A2", 1, 0, "images/Wave1/Day3_20250101/A2/1.jpg", "A3244_A2_age3_view001.jpg"),
    (
        2,
        "A2",
        37,
        1,
        "images/Wave1/Day3_20250101/A2/37.jpg",
        "A3244_A2_age3_view037.jpg",
    ),
    (
        7,
        "B3",
        1,
        0,
        "images/Wave1/Day3_20250101/B3/1.jpg",
        "WEEP-1-4_B3_age3_view001.jpg",
    ),
    (
        7,
        "B3",
        37,
        1,
        "images/Wave1/Day3_20250101/B3/37.jpg",
        "WEEP-1-4_B3_age3_view037.jpg",
    ),
    (9, "C1", 1, 0, "images/Wave1/Day5_20250103/C1/1.jpg", "A3244_C1_age5_view001.jpg"),
    (
        9,
        "C1",
        37,
        1,
        "images/Wave1/Day5_20250103/C1/37.jpg",
        "A3244_C1_age5_view037.jpg",
    ),
    (
        14,
        "D2",
        1,
        0,
        "images/Wave1/Day5_20250103/D2/1.jpg",
        "WEEP-1-4_D2_age5_view001.jpg",
    ),
    (
        14,
        "D2",
        37,
        1,
        "images/Wave1/Day5_20250103/D2/37.jpg",
        "WEEP-1-4_D2_age5_view037.jpg",
    ),
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
        f"_age{row['plant_age_days']}_view{row['view_index']:03d}.jpg"
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
# Blocking review of #40 — even view coverage, monotone plants, stable frame identity
#
# Task 2.7 bought nesting in the view dimension with greedy farthest-point dispersion,
# which is uniform only at powers of two. These pin the replacement: uniform spacing (so
# every count covers the whole cylinder), monotonicity taken from the plant dimension
# alone, and a curated filename that names the view rather than its position — which is
# what actually makes a widened re-selection safe to merge.
# --------------------------------------------------------------------------------------


# Every count from 1 to the full rotation, not a hand-picked list. The first version of
# this test parametrized [1,2,3,4,5,6,8,9,12,24,72] — every value but 5 divides 72, which is
# exactly the region where the property held. Its own assertion went red at 13, 19, 25 and
# 37; those counts were simply not in the list, so a real half-cylinder gap shipped green.
@pytest.mark.parametrize("count", range(1, 73))
def test_views_are_spread_evenly_around_the_full_rotation(count):
    views = ss.select_view_indices(count)
    assert len(views) == count
    assert len(set(views)) == count, "a view was selected twice"
    assert views == sorted(views)
    assert all(1 <= v <= ss.TOTAL_VIEWS for v in views)
    # Circular gaps, including the wrap from the last view back to the first. The old
    # tolerance was `TOTAL_VIEWS // count`, which at count=3 permitted a 24-view spread
    # between the largest and smallest gap — it would not have caught a blind arc even at
    # a count it was run on. A whole number of views cannot divide 72 evenly at every
    # count, but one view of slack is all the scaling needs.
    gaps = [b - a for a, b in zip(views, views[1:])] + [
        ss.TOTAL_VIEWS - views[-1] + views[0]
    ]
    assert max(gaps) - min(gaps) <= 1, f"uneven coverage at n={count}: gaps {gaps}"


def test_the_shipped_default_covers_the_whole_cylinder():
    """RED against task 2.7's greedy dispersion, which sampled half the rotation.

    Greedy farthest-point selection gave ``[1, 19, 37]`` at the documented default — 0,
    90, and 180 degrees — so views 38-72 never contributed ground truth to any package
    built with it, while ``docs/labeling-packages.md`` said views were "dispersed around
    the full rotation".
    """
    views = ss.select_view_indices(3)
    assert views == [1, 25, 49]
    assert max(views) > ss.TOTAL_VIEWS // 2
    assert views != [1, 19, 37]


def test_view_geometry_matches_the_published_label_collections():
    # The eight collections in `wandb-registry-sleap-roots-labels` were selected with a
    # uniform `total_views // views_per_plant` step. New packages have to share their view
    # geometry for "new packages extend the existing corpus" to hold.
    assert ss.select_view_indices(3) == [1, 25, 49]
    assert ss.select_view_indices(4) == [1, 19, 37, 55]


def test_widening_plants_yields_a_superset(tmp_path):
    narrow = run_selection(tmp_path, out_name="a.csv", plants_per_group=1)
    wide = run_selection(tmp_path, out_name="b.csv", plants_per_group=3)
    assert set(narrow["plant_qr_code"]) <= set(wide["plant_qr_code"])


def test_widening_plants_yields_a_superset_of_frames(tmp_path):
    def frames(manifest):
        return set(zip(manifest["scan_id"], manifest["view_index"]))

    narrow = run_selection(
        tmp_path, out_name="a.csv", plants_per_group=1, views_per_plant=4
    )
    wide = run_selection(
        tmp_path, out_name="b.csv", plants_per_group=3, views_per_plant=4
    )
    assert frames(narrow) <= frames(wide)


@pytest.mark.parametrize("narrow,wide", [(2, 4), (3, 4), (3, 6), (4, 8), (2, 5)])
def test_a_curated_filename_names_the_same_view_at_every_selection_width(
    tmp_path, narrow, wide
):
    """RED against task 2.7's positional ``frame_index`` in ``output_filename``.

    The name embedded the frame's position in the selection, so ``..._age3_1.jpg`` was
    view 19 at ``views_per_plant=3`` and view 10 at 5 — the same name, different pixels.
    Decision 6's recovery path is "re-derive wider and republish", and the filename is the
    only key a labeler's corrections carry, so a merge attached one view's root traces to
    another view's image with nothing able to detect it.
    """

    def by_name(manifest):
        return dict(zip(manifest["output_filename"], manifest["view_index"]))

    thin = by_name(
        run_selection(
            tmp_path, out_name="a.csv", plants_per_group=1, views_per_plant=narrow
        )
    )
    thick = by_name(
        run_selection(
            tmp_path, out_name="b.csv", plants_per_group=1, views_per_plant=wide
        )
    )
    shared = set(thin) & set(thick)
    assert shared, "the two selections share no filename, so nothing is being checked"
    for name in shared:
        assert thin[name] == thick[name], name


def test_a_view_that_was_not_selected_before_arrives_under_a_new_name(tmp_path):
    # The other half of the guarantee: non-nested view sets are safe precisely because a
    # newly selected view cannot reuse an existing frame's name.
    narrow = run_selection(
        tmp_path, out_name="a.csv", plants_per_group=1, views_per_plant=3
    )
    wide = run_selection(
        tmp_path, out_name="b.csv", plants_per_group=1, views_per_plant=5
    )
    added = set(zip(wide["scan_id"], wide["view_index"])) - set(
        zip(narrow["scan_id"], narrow["view_index"])
    )
    assert added, "widening selected no new views"
    new_names = set(wide["output_filename"]) - set(narrow["output_filename"])
    assert len(new_names) == len(added)


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
    assert "A3244_A2_age3_view001.jpg" in message
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


def test_the_view_index_appears_in_the_output_filename_not_the_frame_index(tmp_path):
    manifest = run_selection(tmp_path, plants_per_group=1, views_per_plant=3)
    for row in manifest.itertuples():
        assert row.output_filename.endswith(f"_view{row.view_index:03d}.jpg")
    # frame_index remains the within-scan position `build_slp_project` indexes the video
    # by; it is simply no longer what identifies the frame to a human or to a merge.
    assert set(manifest["frame_index"]) == {0, 1, 2}


# --------------------------------------------------------------------------------------
# Blocking review of #40 — malformed and empty inputs fail here, not three stages later
# --------------------------------------------------------------------------------------


def test_a_scans_csv_missing_a_required_column_names_it(tmp_path):
    rows = [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in SCAN_ROWS]
    path = tmp_path / "bad_scans.csv"
    frame = pd.DataFrame(
        rows,
        columns=[
            "scan_id",
            "plant_qr_code",
            "plant_age_days",
            "accession_id",
            "wave_number",
            "scan_path",
        ],
    ).drop(columns=["wave_number"])
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing column"):
        run_selection(tmp_path, scans_csv=path)


def test_a_cleaned_csv_with_no_barcode_column_names_both_accepted_spellings(tmp_path):
    path = tmp_path / "10_final_data.csv"
    pd.DataFrame({"some_trait": [1, 2]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="no plant-barcode column"):
        run_selection(tmp_path, cleaned_csv=path)


def test_a_qc_pool_that_shares_no_barcode_with_scans_csv_fails(tmp_path):
    """RED against the port: an empty pool used to write a header-only manifest.

    The realistic trigger is the one the guide encourages — ``--cleaned-csv`` takes a glob
    (``docs/labeling-packages.md``), so a pattern matching the wrong wave produces a pool
    with no barcode in common and every later stage then reports success.
    """
    cleaned = write_cleaned(tmp_path, barcodes=["NOT_A_REAL_BARCODE"])
    with pytest.raises(ValueError, match="zero barcodes in common"):
        run_selection(tmp_path, cleaned_csv=cleaned)
    assert not (tmp_path / "sample_manifest.csv").exists()


#: A longitudinal fixture: four plants scanned at *both* ages, plus four more that appear
#: only at age 5. Every existing fixture in this module gives each barcode exactly one age,
#: which is the assumption that hid the cross-strata leak — the two groups then select the
#: same plants and the union is a no-op.
LONGITUDINAL_ROWS = [
    (1, "L1", 3, 100, 1, "images/Wave1/Day3/L1"),
    (2, "L2", 3, 100, 1, "images/Wave1/Day3/L2"),
    (3, "L3", 3, 100, 1, "images/Wave1/Day3/L3"),
    (4, "L4", 3, 100, 1, "images/Wave1/Day3/L4"),
    # The same four plants, scanned again at 5 DAG.
    (5, "L1", 5, 100, 1, "images/Wave1/Day5/L1"),
    (6, "L2", 5, 100, 1, "images/Wave1/Day5/L2"),
    (7, "L3", 5, 100, 1, "images/Wave1/Day5/L3"),
    (8, "L4", 5, 100, 1, "images/Wave1/Day5/L4"),
    # Four that germinated late and exist only at 5 DAG, so the two groups differ.
    (9, "L5", 5, 100, 1, "images/Wave1/Day5/L5"),
    (10, "L6", 5, 100, 1, "images/Wave1/Day5/L6"),
    (11, "L7", 5, 100, 1, "images/Wave1/Day5/L7"),
    (12, "L8", 5, 100, 1, "images/Wave1/Day5/L8"),
]


def test_a_plant_selected_at_one_age_does_not_drag_in_its_other_ages(tmp_path):
    """RED against the port: per-group selections were unioned, then applied by barcode.

    A plant selected in (age 3, accession 100) pulled in every scan it had at every other
    age, whether or not (age 5, accession 100) had selected it. The plants double-counted
    are exactly the ones present in more groups — survivors — and survivorship correlates
    with vigor, so the label set skewed toward healthy plants while the README and the
    metadata both reported the *requested* plants_per_group.
    """
    scans = write_scans(tmp_path / "longitudinal", rows=LONGITUDINAL_ROWS)
    cleaned = write_cleaned(
        tmp_path, barcodes=sorted({row[1] for row in LONGITUDINAL_ROWS})
    )

    manifest = run_selection(
        tmp_path, scans_csv=scans, cleaned_csv=cleaned, plants_per_group=2
    )

    per_group = manifest.groupby(["plant_age_days", "accession_id"])[
        "plant_qr_code"
    ].nunique()
    assert per_group.to_dict() == {(3, 100): 2, (5, 100): 2}


def test_a_group_smaller_than_the_request_is_reported_not_silently_taken_whole(
    tmp_path, caplog
):
    """Realized counts, not the requested one.

    A group smaller than the request is taken whole, which is legitimate — but nothing
    reported it, so "5 plants per age x accession group" in the README was a request
    presented as a result.
    """
    scans = write_scans(tmp_path / "longitudinal", rows=LONGITUDINAL_ROWS)
    cleaned = write_cleaned(
        tmp_path, barcodes=sorted({row[1] for row in LONGITUDINAL_ROWS})
    )

    with caplog.at_level("WARNING"):
        run_selection(
            tmp_path, scans_csv=scans, cleaned_csv=cleaned, plants_per_group=6
        )

    # Age 3 holds only four plants; age 5 holds eight and is satisfied.
    assert "1 of 2 group(s) hold fewer than the 6 plant(s) requested" in caplog.text
    assert "(age 3, accession 100): 4" in caplog.text


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_plants_per_group_fails_instead_of_slicing(tmp_path, bad):
    """RED against the port: the prefix slice gave Python's semantics to a bad value.

    ``ordered[:0]`` selects nothing and ``ordered[:-1]`` drops the last plant of every
    group, both writing a manifest and exiting 0. ``views_per_plant`` was validated;
    these two were not.
    """
    with pytest.raises(ValueError, match="must be a positive integer"):
        run_selection(tmp_path, plants_per_group=bad)
    assert not (tmp_path / "sample_manifest.csv").exists()


@pytest.mark.parametrize("option", ["--plants-per-group", "--views-per-plant"])
@pytest.mark.parametrize("bad", ["0", "-1"])
def test_the_cli_rejects_a_non_positive_count_before_doing_any_work(
    tmp_path, option, bad
):
    from click.testing import CliRunner

    from sleap_roots_training.cli import main

    result = CliRunner().invoke(
        main,
        [
            "labeling",
            "select",
            "--cleaned-csv",
            str(write_cleaned(tmp_path)),
            "--scans-csv",
            str(write_scans(tmp_path)),
            "--output-csv",
            str(tmp_path / "sample_manifest.csv"),
            option,
            bad,
        ],
    )

    assert result.exit_code != 0
    assert "is not in the range" in result.output or "Invalid value" in result.output
    assert not (tmp_path / "sample_manifest.csv").exists()


@pytest.mark.parametrize("column", ["plant_age_days", "accession_id"])
def test_a_null_grouping_key_fails_instead_of_dropping_the_plant(tmp_path, column):
    """RED against the port: ``groupby`` dropped these rows with no error and no log.

    The operator doc's own Phase 0 recipe left-joins a fresh accession map onto the scan
    table, so every plant the map does not cover arrives with a blank ``accession_id`` —
    and the plants that vanish are typically a whole accession or wave, not a random
    subset, so the package reports success while under-representing them.
    """
    path = tmp_path / "nulls.csv"
    frame = pd.DataFrame(
        SCAN_ROWS,
        columns=[
            "scan_id",
            "plant_qr_code",
            "plant_age_days",
            "accession_id",
            "wave_number",
            "scan_path",
        ],
    )
    frame.loc[frame["plant_qr_code"].isin(["A1", "A2"]), column] = None
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match=f"have no {column!r}"):
        run_selection(tmp_path, scans_csv=path, plants_per_group=99)


def test_the_accession_id_renders_as_a_whole_number_in_every_filename(tmp_path):
    """The age was cast and the accession id was not, so one bad cell renamed everything.

    A null anywhere in `accession_id` types the whole column `float64`. On the no-map path
    (legal, and warned) every curated filename then read `100.0_A2_age3_view001.jpg`, and
    the manifest carried `.0` into the accession column #10's `LabelCard` reads — the same
    comparability break the age cast exists to prevent, one column over.
    """
    frame = pd.DataFrame(
        SCAN_ROWS,
        columns=[
            "scan_id",
            "plant_qr_code",
            "plant_age_days",
            "accession_id",
            "wave_number",
            "scan_path",
        ],
    )
    # Force the float64 typing a null elsewhere in the column would cause, without a null
    # in a row that survives the QC filter.
    frame["accession_id"] = frame["accession_id"].astype(float)
    path = tmp_path / "float_accessions.csv"
    frame.to_csv(path, index=False)

    manifest = run_selection(
        tmp_path, scans_csv=path, accession_names=None, plants_per_group=1
    )

    assert all(".0_" not in name for name in manifest["output_filename"])
    assert set(manifest["accession_name"]) == {"100", "200"}


def test_a_float_typed_accession_column_still_matches_the_supplied_map(tmp_path):
    # The coverage check and the filename must normalize identically, or a legitimate map
    # would be reported as incomplete.
    frame = pd.DataFrame(
        SCAN_ROWS,
        columns=[
            "scan_id",
            "plant_qr_code",
            "plant_age_days",
            "accession_id",
            "wave_number",
            "scan_path",
        ],
    )
    frame["accession_id"] = frame["accession_id"].astype(float)
    path = tmp_path / "float_accessions.csv"
    frame.to_csv(path, index=False)

    manifest = run_selection(tmp_path, scans_csv=path, plants_per_group=1)

    assert set(manifest["accession_name"]) == {"A3244", "WEEP-1-4"}


def test_the_age_renders_as_a_whole_number_in_every_filename(tmp_path):
    # One NaN anywhere in the column types it float64, which used to render `age3.0` for
    # every row in the package — a comparability break against the published collections
    # caused by a single bad cell elsewhere in the table.
    manifest = run_selection(tmp_path, plants_per_group=1)
    assert all("age3.0" not in name for name in manifest["output_filename"])
    assert manifest["plant_age_days"].dtype.kind == "i"


@pytest.mark.parametrize(
    "accession_name,reason",
    [
        ("../../pwn", "path separator"),
        ("a/b", "path separator"),
        ("a\\b", "path separator"),
        ("PI:594301", "Windows reserves"),
        ("what?", "Windows reserves"),
    ],
)
def test_an_output_filename_that_is_not_a_bare_filename_fails(
    tmp_path, accession_name, reason
):
    """RED against the port: these reached ``shutil.copy2`` and wrote outside the package.

    ``accession_name`` is pasted by hand (design.md F2) and ``plant_qr_code`` is copied
    verbatim from Bloom, so both reach the filesystem unvalidated. ``metadata`` already
    rejects a bad ``experiment`` for exactly this reason; the two fields that vary per
    package were the ones left unchecked.
    """
    with pytest.raises(ValueError, match=reason):
        run_selection(
            tmp_path,
            accession_names={100: accession_name, 200: "WEEP-1-4"},
            plants_per_group=1,
        )
    assert not (tmp_path / "sample_manifest.csv").exists()


def test_an_incomplete_accession_map_is_rejected_at_selection(tmp_path):
    """RED against the port: an unmapped id fell back to its number and built anyway.

    That is the exact fallback ``render_readme`` refuses at build time, calling it a
    package that documents its genotypes as numbers — so the map was accepted here,
    carried into every curated filename, and rejected three stages later, at which point
    completing it renamed every file in the package.
    """
    with pytest.raises(ValueError, match="does not cover accession id"):
        run_selection(tmp_path, accession_names={100: "A3244"}, plants_per_group=1)
    assert not (tmp_path / "sample_manifest.csv").exists()


def test_accession_ids_resolve_whether_the_map_is_keyed_by_int_or_string(tmp_path):
    # `select` used to coerce keys to int and `build` kept them as strings, so a
    # non-numeric accession id worked for one entry point and raised for the other.
    by_int = run_selection(
        tmp_path, out_name="a.csv", accession_names=ACCESSION_NAMES, plants_per_group=1
    )
    by_str = run_selection(
        tmp_path,
        out_name="b.csv",
        accession_names={str(k): v for k, v in ACCESSION_NAMES.items()},
        plants_per_group=1,
    )
    pd.testing.assert_frame_equal(by_int, by_str)


def test_omitting_the_accession_map_warns_that_filenames_will_carry_numbers(
    tmp_path, caplog
):
    with caplog.at_level("WARNING"):
        manifest = run_selection(tmp_path, accession_names=None, plants_per_group=1)

    assert "No accession names supplied" in caplog.text
    assert all(
        name.startswith(("100_", "200_")) for name in manifest["output_filename"]
    )


def test_backslash_paths_in_scans_csv_normalize_through_the_shared_helper(tmp_path):
    """The rule is one function now, so both producers' paths are normalized identically.

    ``scans.csv``'s own ``scan_path`` normalization had no backslash coverage at all,
    despite design.md F11 recording that the real shipped WEEP manifest carried Windows
    paths — and selection had its own inlined copy of the rule the copy step also
    implements, which is the duplication this consolidates.
    """
    from sleap_roots_training.labeling.copy_images import _posix

    assert ss.posix_path is _posix
    assert str(ss.posix_path("images\\Wave1\\Day3\\A2")) == "images/Wave1/Day3/A2"
    assert str(ss.posix_path("./images/Wave1")) == "images/Wave1"


def test_filenames_colliding_only_in_case_are_rejected(tmp_path):
    """RED against the port: byte-exact uniqueness passed, then macOS lost a frame.

    The copy step counted every ``shutil.copy2`` call it made, so it reported the full row
    count with one fewer file on disk — the design.md F5 silent partial copy that step
    claims to have eliminated, reintroduced by two accession names differing in case.
    """
    # The same plant at the same age under two accession ids whose hand-typed names differ
    # only in case. Byte-exact uniqueness sees two names; the filesystem sees one file.
    scans = write_scans(
        tmp_path / "case",
        rows=SCAN_ROWS
        + [(18, "A2", 3, 200, 1, "images/Wave1/Day3_20250101/A2_rescan")],
    )
    with pytest.raises(ValueError, match="once case is folded"):
        run_selection(
            tmp_path,
            scans_csv=scans,
            accession_names={100: "WEEP-1-4", 200: "weep-1-4"},
            plants_per_group=99,
        )
    assert not (tmp_path / "sample_manifest.csv").exists()


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
