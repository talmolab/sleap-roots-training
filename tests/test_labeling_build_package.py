"""Characterization + deviation tests for the package builder.

Sequenced per design.md Decision 1. The ``characterization`` tests pin what the port
inherited unchanged from the vault's ``build_slp_project.py``; the ``deviation`` tests pin
what tasks 4.4–4.7 change on purpose, each naming the legacy behavior it replaced — above
all F1's silent-empty build, where an unpopulated ``images/`` warned per scan, wrote both
``.slp`` files, and returned normally. ``embed=False`` is still characterized here; section
5 is the commit that changes it.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
import sleap_io as sio

from conftest import (
    METADATA,
    SCANS,
    VIEWS,
    build_projects,
    build_inputs,
    manifest_rows,
    primary,
    write_jpeg,
    write_manifest,
    write_predictions,
)
import pandas as pd

from sleap_roots_training.labeling import build_package as bp
from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.build_package import build_slp_project
from sleap_roots_training.labeling.metadata import PackageMetadata

# --------------------------------------------------------------------------------------
# Characterization — behavior the port inherited unchanged
# --------------------------------------------------------------------------------------


def test_writes_both_root_type_projects_under_versioned_names(tmp_path):
    output_dir = build_projects(tmp_path)

    assert (output_dir / "soybean_weep_primary_labels.v000.slp").is_file()
    assert (output_dir / "soybean_weep_lateral_labels.v000.slp").is_file()


def test_the_version_string_is_part_of_the_filename(tmp_path):
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)

    build_slp_project(
        manifest_csv, images_dir, predictions_dir, output_dir, METADATA, "v003"
    )

    assert (output_dir / "soybean_weep_primary_labels.v003.slp").is_file()


def test_one_video_per_scan_holding_only_the_selected_views(tmp_path):
    """The sleap-roots convention: one video per cylinder scan, not one per image."""
    labels = primary(build_projects(tmp_path))

    assert len(labels.videos) == 2
    for video in labels.videos:
        assert video.shape[0] == 3


def test_frames_land_at_their_within_scan_position_carrying_the_predictions(tmp_path):
    labels = primary(build_projects(tmp_path))

    assert len(labels.labeled_frames) == 6
    per_video = {}
    for lf in labels.labeled_frames:
        per_video.setdefault(id(lf.video), []).append(lf.frame_idx)
    assert sorted(per_video.values()) == [[0, 1, 2], [0, 1, 2]]
    assert all(lf.instances for lf in labels.labeled_frames)


def test_a_frames_prediction_is_the_one_from_its_own_view(tmp_path):
    """The 1-based view index maps onto the prediction file's 0-based rotation index.

    The fixture encodes each prediction's view in its x coordinate, so an off-by-one in
    that translation would put another angle's landmarks on this frame — the corruption
    that is invisible in a built package.
    """
    labels = primary(build_projects(tmp_path))

    by_position = {}
    for lf in labels.labeled_frames:
        by_position.setdefault(lf.frame_idx, set()).add(
            float(lf.instances[0].points[0]["xy"][0])
        )
    assert by_position == {0: {1.0}, 1: {25.0}, 2: {49.0}}


def test_instances_are_rebuilt_against_one_canonical_skeleton(tmp_path):
    """Aggregating N prediction files must not leave N duplicate skeletons behind."""
    labels = primary(build_projects(tmp_path))

    assert len(labels.skeletons) == 1
    assert all(
        lf.instances[0].skeleton is labels.skeletons[0] for lf in labels.labeled_frames
    )


def test_the_hardcoded_soybean_skeletons_are_what_gets_written(tmp_path):
    """Pins Decision 7's starting point: one crop, hand-edited per crop, 6 and 4 nodes."""
    output_dir = build_projects(tmp_path)

    primary_labels = primary(output_dir)
    lateral_labels = sio.load_slp(
        str(output_dir / "soybean_weep_lateral_labels.v000.slp")
    )
    assert primary_labels.skeletons[0].name == "soybean_primary"
    assert [n.name for n in primary_labels.skeletons[0].nodes] == [
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
        "r6",
    ]
    assert lateral_labels.skeletons[0].name == "soybean_lateral"
    assert len(lateral_labels.skeletons[0].nodes) == 4


def test_a_scan_predicted_for_only_one_root_type_fails_the_build(tmp_path):
    """RED against the port, which warned and wrote a short ``.slp``.

    The only fatal case used to be a prediction file that was totally absent for *every*
    root type. A scan predicted for primary but not lateral fell through to
    ``logger.warning("Scan %s contributes no %s labels")`` and the build succeeded — with
    the lateral project three frames shorter than the manifest and nothing downstream
    counting.

    This is the "never asked" case, not the "asked and found nothing" case: there is no
    lateral prediction file at all, so no frame of this scan was ever evaluated for
    laterals. Skipping those would drop exactly the frames the model could not detect. A
    frame the model *did* evaluate and found nothing in ships empty instead — see
    ``test_a_frame_the_model_found_nothing_in_ships_empty_rather_than_vanishing``.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_2.*.root_lateral.slp"):
        path.unlink()

    with pytest.raises(ValueError, match="do not cover every selected view") as exc:
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )
    assert "scan_id 2" in str(exc.value) and "lateral" in str(exc.value)
    assert not list(output_dir.glob("*.slp"))


def test_predictions_that_miss_the_selected_views_fail_the_build(tmp_path):
    """The realistic trigger: the file exists, but covers the wrong frame range.

    Prediction ``.slp`` files commonly hold only the frames where instances were found, so
    a partial pipeline run — or predictions generated against a different view spread —
    produces exactly this. The absent-file guard never saw it.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_2.*.root_lateral.slp"):
        path.unlink()
    # Present, well-formed, and covering views this package did not select.
    write_predictions(predictions_dir, 2, "lateral", view_indices=(7, 31, 55))

    with pytest.raises(ValueError, match="do not cover every selected view"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )
    assert not list(output_dir.glob("*.slp"))


def test_multiple_prediction_files_for_a_scan_warn_and_use_the_first(tmp_path, caplog):
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    write_predictions(predictions_dir, 1, "primary", model="model_b")

    with caplog.at_level("WARNING"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )

    assert "Multiple primary predictions for scan 1" in caplog.text


def test_embedding_keeps_the_source_image_paths_as_provenance(tmp_path):
    """Task 5.2 replaced ``embed=False``; the paths it used to depend on are still recorded.

    ``source_video`` is provenance, not a dependency — nothing opens it — so a consumer
    can still see which curated images a frame came from without the package needing them
    to exist. The self-containment guarantee itself is in ``test_labeling_embed.py``.
    """
    output_dir = build_projects(tmp_path)
    labels = primary(output_dir)

    referenced = Path(labels.videos[0].source_video.filename[0])
    assert referenced.parent == (output_dir / "images")


# --------------------------------------------------------------------------------------
# Deviation (tasks 4.4-4.7) — nothing is written until everything checks out
# --------------------------------------------------------------------------------------


def test_an_unpopulated_images_dir_fails_the_build_and_writes_nothing(tmp_path):
    """Replaces design.md F1, the second link in the silent-empty chain.

    The vault script warned per scan, wrote both ``.slp`` files, and returned normally —
    an empty labeling package that looked like a completed build, and the one the copy
    step used to hand it. All the missing images are reported together, since the useful
    fact is "the copy step never ran", not "scan 1 failed".
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, populate_images=False
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )

    assert "6 of 6" in str(excinfo.value)
    assert "A3244_9DK8KJJEZR_age3_0.jpg" in str(excinfo.value)
    assert list(output_dir.glob("*.slp")) == []


def test_a_single_missing_curated_image_fails_the_build(tmp_path):
    """A partial ``images/`` is no more buildable than an empty one."""
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    (images_dir / "A3244_9DK8KJJEZR_age3_1.jpg").unlink()

    with pytest.raises(FileNotFoundError, match="A3244_9DK8KJJEZR_age3_1.jpg"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )


def test_a_failed_build_leaves_no_output_directory_behind(tmp_path):
    """Task 4.5: no partial package a later step could mistake for a complete one."""
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    output_dir = tmp_path / "fresh_package"
    (images_dir / "A3244_9DK8KJJEZR_age3_1.jpg").unlink()

    with pytest.raises(FileNotFoundError):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )

    assert not output_dir.exists()


def test_a_scan_with_no_predictions_at_all_fails_the_build(tmp_path):
    """The vault script skipped it, so the package silently omitted a selected scan.

    Reported separately from a scan predicted for only *some* declared root types, which
    also fails now (blocking review of #40) but points at a different fix: a scan absent
    from every prediction file means the selection cannot be honored at all, while a scan
    short one root type usually means the predictions do not cover the selected views.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_2.*"):
        path.unlink()

    with pytest.raises(ValueError, match="no predictions"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )


def test_an_empty_manifest_fails_on_its_own_terms(tmp_path):
    """RED against the port: this died as ``KeyError: 'pop from an empty set'``.

    An empty manifest reached ``skeleton_for`` with no ages, and the raw ``KeyError`` it
    raised there is not in ``cli.py``'s ``except (OSError, ValueError)`` — so the operator
    got a traceback blaming the skeleton table for an empty selection three stages
    upstream.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    write_manifest(manifest_csv, [])

    with pytest.raises(ValueError, match="has no rows"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )
    assert not list(output_dir.glob("*.slp"))


@pytest.mark.parametrize(
    "column", ["scan_id", "plant_age_days", "view_index", "frame_index"]
)
def test_a_manifest_missing_a_column_the_builder_reads_names_it(tmp_path, column):
    """RED against the port: a renamed column escaped the CLI as a bare ``KeyError``.

    The copy step validates its own required columns and does it well; the builder reads
    four more that nothing checked, so a manifest that passed the copy step still died
    with a traceback here.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    rows = list(csv.DictReader(manifest_csv.open()))
    remaining = [c for c in ss.MANIFEST_COLUMNS if c != column]
    with manifest_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=remaining, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match=f"missing required column\\(s\\): {column}"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )


@pytest.mark.parametrize(
    "nodes,detail",
    [
        # The dangerous one: same nodes, reversed. The count matches, so only an order
        # check catches it — and getting it wrong inverts every root's polarity.
        (["r6", "r5", "r4", "r3", "r2", "r1"], "different order"),
        (["a", "b", "c", "d", "e", "f"], "different node names"),
    ],
)
def test_predictions_whose_nodes_do_not_match_the_skeleton_fail(
    tmp_path, nodes, detail
):
    """RED against the port: the rebind is positional and only the *count* was checked.

    A model emitting the chain tip-first would be rebound to ``r1..rN`` base-first without
    complaint. Every root angle and base/tip anchoring in the resulting ground truth would
    be reversed, and the labeler would see plausible points and correct their positions
    rather than their order — so the corruption survives labeling and reaches the corpus.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_1.*.root_primary.slp"):
        path.unlink()
    write_predictions(predictions_dir, 1, "primary", node_names=nodes)

    with pytest.raises(ValueError, match=detail) as exc:
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )
    assert "soybean_primary" in str(exc.value)
    assert not list(output_dir.glob("*.slp"))


def test_a_node_count_mismatch_names_the_skeleton_and_both_counts(tmp_path):
    """RED against the port: numpy raised, naming neither side of the disagreement.

    This is the one place the advisory skeleton table is checked against reality — the
    table says what a labeler places, the predictions carry whatever the model produced —
    and it used to do that check by accident, as `could not broadcast input array from
    shape (6,) into shape (4,)`.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, predictions=(("primary", 6), ("lateral", 9))
    )

    with pytest.raises(ValueError, match="node") as excinfo:
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )

    message = str(excinfo.value)
    assert "soybean_lateral" in message
    assert "9" in message and "4" in message
    assert "skeletons.yaml" in message


def test_a_frame_the_model_found_nothing_in_ships_empty_rather_than_vanishing(tmp_path):
    """A true negative is a result, and the corpus could not previously record one.

    An all-NaN instance is not an observation, so it is dropped — but dropping the *frame*
    with it made genuine absence (a young plant with no lateral roots) indistinguishable
    from predictions covering the wrong views, and the build failed on both. The only ways
    out were to re-run prediction or to drop the root type, and dropping it reintroduces
    the same bias at package granularity. The frame now ships empty, so the labeler can
    open it and confirm nothing is there.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_1.*.root_lateral.slp"):
        path.unlink()
    write_predictions(predictions_dir, 1, "lateral", node_count=4, all_nan=True)

    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)

    lateral = sio.load_slp(str(output_dir / "soybean_weep_lateral_labels.v000.slp"))
    # One frame per manifest row, as the spec requires — scan 1's three carry nothing.
    assert len(lateral.labeled_frames) == 6
    empty = [lf for lf in lateral.labeled_frames if not lf.instances]
    assert len(empty) == 3
    # And the pixels are still embedded, so a labeler can open the frame to confirm.
    assert empty[0].image.shape[0] > 0


def test_an_all_nan_instance_is_not_shipped_as_a_label(tmp_path):
    """The instance is still dropped; only the frame survives it.

    The check was `if instances:` — list non-emptiness — so an instance whose every
    keypoint is NaN counted as a contribution, and the labeler opened a frame carrying an
    instance with nothing visible in it.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_1.*.root_lateral.slp"):
        path.unlink()
    write_predictions(predictions_dir, 1, "lateral", node_count=4, all_nan=True)

    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)

    lateral = sio.load_slp(str(output_dir / "soybean_weep_lateral_labels.v000.slp"))
    located = [inst for lf in lateral.labeled_frames for inst in lf.instances]
    assert len(located) == 3, "only scan 2's real predictions should survive"
    assert not any(
        np.all(np.isnan(np.asarray(inst.points["xy"], dtype=float))) for inst in located
    )


def test_a_root_type_empty_in_every_frame_fails_the_build(tmp_path):
    """An empty frame is a result; a project that is empty throughout is not.

    The labeler would be handed a whole project with nothing in it to correct, which means
    the predictions for that root type are absent or the package should not declare it.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("*.root_lateral.slp"):
        path.unlink()
    for scan_id, *_ in SCANS:
        write_predictions(
            predictions_dir, scan_id, "lateral", node_count=4, all_nan=True
        )

    with pytest.raises(ValueError, match="no predicted instance in any frame") as exc:
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )
    assert "lateral" in str(exc.value)
    assert not list(output_dir.glob("*.slp"))


def test_an_instance_with_some_missing_keypoints_is_kept(tmp_path):
    """The other half: an occluded or early-terminating lateral root is real data.

    Every fixture in this module places all nodes, so nothing exercised partial NaN — the
    common real-world case. Its visible nodes are a genuine starting point for a labeler,
    so it must survive the all-NaN filter above.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_1.*.root_lateral.slp"):
        path.unlink()
    write_predictions(predictions_dir, 1, "lateral", node_count=4, nan_from=2)

    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)

    lateral = sio.load_slp(str(output_dir / "soybean_weep_lateral_labels.v000.slp"))
    assert len(lateral.labeled_frames) == 6
    points = lateral.labeled_frames[0].instances[0].points["xy"]
    assert not np.isnan(points[0]).any()
    assert np.isnan(points[2]).all()


def test_a_package_whose_ages_straddle_a_skeleton_split_is_refused(tmp_path):
    """The rice 5/6-DAG boundary guard, which no test reached before.

    Its whole purpose is preventing half a package being labeled against the wrong node
    count. The table splits rice into young 2-5 DAG (primary and crown) and old 6-10 DAG
    (crown only), so a manifest spanning that boundary has no single answer.
    """
    rice = PackageMetadata(
        species="rice", mode="cylinder", experiment="weep", root_types=("crown",)
    )
    straddling = [
        {**row, "plant_age_days": 5 if row["scan_id"] == 1 else 7}
        for row in manifest_rows()
    ]
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, rows=straddling, predictions=(("crown", 6),)
    )

    with pytest.raises(ValueError, match="more than one skeleton"):
        build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, rice)


def test_a_requested_root_type_with_no_frames_fails_the_build(tmp_path):
    """Task 4.4: an empty selection is never a successful build.

    Declaring a root type the package has no labels for is exactly the empty ``.slp``
    the vault script wrote without complaint.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("*.root_lateral.slp"):
        path.unlink()

    with pytest.raises(ValueError, match="lateral"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )


def test_a_package_may_declare_a_single_root_type(tmp_path):
    """The way to build a primary-only package is to say so, not to ship an empty file."""
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("*.root_lateral.slp"):
        path.unlink()
    metadata = PackageMetadata(
        species="soybean", mode="cylinder", experiment="weep", root_types=("primary",)
    )

    written = build_slp_project(
        manifest_csv, images_dir, predictions_dir, output_dir, metadata
    )

    assert set(written) == {"primary"}
    assert not (output_dir / "soybean_weep_lateral_labels.v000.slp").exists()


def test_a_species_the_table_does_not_cover_fails_before_reading_anything(tmp_path):
    """Skeletons are resolved first, so this is not reported as a data problem.

    Pennycress is in ``SPECIES_VOCAB`` and has two ``model_selection.yaml`` rows, but the
    skeleton table's source omits it. Defaulting to another crop's node counts would
    produce a package that looks fine and cannot be combined with anything, so it fails —
    with an unpopulated ``images/`` here, proving the check runs before the data does.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, populate_images=False
    )
    metadata = PackageMetadata(
        species="pennycress",
        mode="cylinder",
        experiment="weep",
        root_types=("primary",),
    )

    with pytest.raises(ValueError, match="pennycress"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, metadata
        )


# --------------------------------------------------------------------------------------
# Obligation from task 2.10 — one authoritative frame-position derivation
# --------------------------------------------------------------------------------------


def test_frame_position_comes_from_the_manifest_not_from_sorting_view_index(tmp_path):
    """The builder reads ``frame_index``; it no longer re-derives position.

    2.10 pinned ``frame_index`` as authoritative and proved the vault script's
    sort-by-``view_index``-and-enumerate agrees with it *today* — they diverge only for a
    manifest whose frame order is not view order. This fixture manufactures exactly that:
    with the indices reversed, the old derivation would place view 49 at position 2 and
    this one places it at position 0, so the test fails if the second derivation ever
    comes back.
    """
    rows = list(manifest_rows(frame_indices=[2, 1, 0]))
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, rows=rows
    )

    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)

    labels = primary(output_dir)
    by_position = {}
    for lf in labels.labeled_frames:
        by_position.setdefault(lf.frame_idx, set()).add(
            float(lf.instances[0].points[0]["xy"][0])
        )
    assert by_position == {0: {49.0}, 1: {25.0}, 2: {1.0}}
    # ...and the video's frames are in that same order, so frame 0 really is view 49's
    # image. A position that indexed a differently-ordered video would be a wrong package.
    assert Path(labels.videos[0].source_video.filename[0]).name.endswith("_age3_0.jpg")


def test_frame_position_ignores_view_order_when_frame_index_is_already_ascending(
    tmp_path,
):
    """The mirror of the test above, and the case F3-revisited made worth pinning.

    Suggestion, third review of #40. The 2.10 test varies ``frame_index`` while the views
    stay ascending; this varies the *views* while ``frame_index`` is a plain ``0, 1, 2``.
    Both derivations are then reading a well-formed manifest and disagreeing: sorting on
    ``view_index`` would put view 1 at position 0, and reading ``frame_index`` puts view 49
    there.

    Worth a durable test rather than a note because F6 recorded that "the two derivations
    agree today only because ``selected_views`` is ascending" — an incidental property of
    the selector, which the review's own F3-revisited change then made *less* incidental:
    ``output_filename`` names the view now, so a frame's identity no longer travels through
    its position, and a manifest whose rows are not in view order stops being a thing only
    a hand-edit could produce.
    """
    rows = list(manifest_rows(views=(49, 25, 1)))
    assert [row["frame_index"] for row in rows[:3]] == [0, 1, 2]
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, rows=rows
    )

    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)

    labels = primary(output_dir)
    by_position = {}
    for lf in labels.labeled_frames:
        by_position.setdefault(lf.frame_idx, set()).add(
            float(lf.instances[0].points[0]["xy"][0])
        )
    # Position 0 is view 49 because the manifest says so, not view 1 because it sorts first.
    assert by_position == {0: {49.0}, 1: {25.0}, 2: {1.0}}
    assert Path(labels.videos[0].source_video.filename[0]).name.endswith("_age3_0.jpg")


def test_a_non_contiguous_frame_index_fails_rather_than_mis_indexing(tmp_path):
    """``frame_index`` is a position into the scan's video, so it must be a rank from zero."""
    rows = list(manifest_rows(frame_indices=[0, 1, 7]))
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, rows=rows
    )

    with pytest.raises(ValueError, match="frame_index"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )


# --------------------------------------------------------------------------------------
# Blocking review of #40, second pass — the embed memory ceiling
# --------------------------------------------------------------------------------------


def test_a_payload_larger_than_the_ceiling_fails_before_anything_is_written(
    tmp_path, monkeypatch
):
    """`save_slp(embed=True)` holds every encoded frame in RAM before writing.

    Measured at roughly 1:1 with the payload, so a widened collection is killed by the OS
    on a 4 GB pod — and SIGKILL runs no `except` handler, so `package.py`'s staging cleanup
    never runs and a full package's worth of bytes is left behind. Before the allocation is
    the only place this can be caught.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    # A ceiling below the fixture's few hundred bytes of curated JPEGs.
    monkeypatch.setenv(bp.EMBED_CEILING_ENV, "16")

    with pytest.raises(ValueError, match="ceiling") as exc:
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )

    assert bp.EMBED_CEILING_ENV in str(exc.value)
    assert not list(output_dir.glob("*.slp"))


def test_the_ceiling_defaults_to_two_gibibytes_and_permits_a_real_package(tmp_path):
    assert bp.EMBED_PAYLOAD_CEILING_BYTES == 2 * 1024**3
    # The positive control: a normal package is nowhere near it.
    build_projects(tmp_path)


@pytest.mark.parametrize("bad", ["not-a-number", "0", "-1"])
def test_an_unusable_ceiling_override_falls_back_rather_than_failing_the_build(
    tmp_path, monkeypatch, caplog, bad
):
    # A bad *setting* should not be the thing that stops a build, but it must be said.
    monkeypatch.setenv(bp.EMBED_CEILING_ENV, bad)

    with caplog.at_level("WARNING"):
        build_projects(tmp_path)

    assert bp.EMBED_CEILING_ENV in caplog.text


# --------------------------------------------------------------------------------------
# Blocking review of #40, second pass — which model produced the starting points
# --------------------------------------------------------------------------------------


def test_the_predicting_models_are_reported_for_the_manifests_scans(tmp_path):
    """Labelers anchor on the predictions, so the model is a confounder in the result.

    Two packages built from different models were indistinguishable in the artifact.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    manifest = pd.read_csv(manifest_csv)

    assert bp.prediction_models(manifest, predictions_dir, METADATA.root_types) == (
        "model_a",
    )


def test_the_reported_model_is_the_one_the_builder_actually_reads(tmp_path):
    """Both go through `prediction_file_for`, so they cannot disagree.

    A provenance record naming a different file than the build used would be worse than
    none — and the builder's tie-break (sorted, first) is not self-evident.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    write_predictions(predictions_dir, 1, "primary", model="model_z")
    manifest = pd.read_csv(manifest_csv)

    chosen = bp.prediction_file_for(1, predictions_dir, "primary")
    reported = bp.prediction_models(manifest, predictions_dir, ("primary",))

    # Two candidate files exist for scan 1; the builder takes the first sorted match, and
    # provenance records *that* one and not the other. Recording a model the build did not
    # read would be worse than recording none.
    assert "model_a" in chosen.name
    assert "model_z" not in chosen.name
    assert reported == ("model_a",)
