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

from conftest import write_jpeg
from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.build_package import build_slp_project
from sleap_roots_training.labeling.metadata import PackageMetadata

#: Two scans, three selected views each. The view indices are the vault script's own
#: three-view spread, so the frame/view correspondence under test is the shipped one.
SCANS = (
    (1, "9DK8KJJEZR", 3, 12742739, "A3244"),
    (2, "8XQ2LMNPQR", 3, 12742740, "WEEP-1-4"),
)
VIEWS = (1, 25, 49)

#: The soybean WEEP package the vault script was hand-edited to build.
METADATA = PackageMetadata(
    species="soybean", mode="cylinder", root_types=("primary", "lateral")
)


def manifest_rows(scans=SCANS, views=VIEWS, frame_indices=None):
    """Build manifest row dicts, letting a test decouple frame_index from view order."""
    for scan_id, qr, age, acc_id, acc_name in scans:
        indices = frame_indices if frame_indices is not None else range(len(views))
        for frame_index, view_index in zip(indices, views):
            scan_path = f"images/Wave1/Day{age}_20250101/{qr}"
            yield {
                "scan_id": scan_id,
                "plant_qr_code": qr,
                "plant_age_days": age,
                "accession_id": acc_id,
                "accession_name": acc_name,
                "wave_number": 1,
                "view_index": view_index,
                "frame_index": frame_index,
                "source_scan_path": scan_path,
                "source_image": f"{scan_path}/{view_index}.jpg",
                "output_filename": f"{acc_name}_{qr}_age{age}_{frame_index}.jpg",
            }


def write_manifest(path: Path, rows) -> list[dict]:
    """Write ``sample_manifest.csv`` and return the rows written."""
    rows = list(rows)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_predictions(
    predictions_dir: Path,
    scan_id: int,
    root_type: str,
    view_indices=VIEWS,
    node_count: int = 6,
    model: str = "model_a",
) -> Path:
    """Write one scan's prediction ``.slp``, as the traits pipeline emits it.

    Prediction frames are indexed over the *full* rotation (``view_index - 1``), not over
    the selected subset — the offset the builder has to translate.
    """
    predictions_dir.mkdir(parents=True, exist_ok=True)
    nodes = [f"r{i}" for i in range(1, node_count + 1)]
    skeleton = sio.Skeleton(
        nodes=nodes,
        edges=[(nodes[i], nodes[i + 1]) for i in range(node_count - 1)],
        name=f"pred_{root_type}",
    )
    # The pipeline predicts on the scan's own container, not on the curated images; it is
    # never opened here (`open_videos=False`), only its frame indices are read.
    video = sio.Video(filename=f"/scans/scan_{scan_id}.h5", open_backend=False)
    frames = []
    for view_index in view_indices:
        points = np.array(
            [[float(view_index), float(i)] for i in range(node_count)], dtype=np.float64
        )
        instance = sio.PredictedInstance.from_numpy(
            points_data=points,
            skeleton=skeleton,
            point_scores=np.full(node_count, 0.9),
            score=0.85,
        )
        frames.append(
            sio.LabeledFrame(
                video=video, frame_idx=view_index - 1, instances=[instance]
            )
        )
    labels = sio.Labels(labeled_frames=frames, videos=[video], skeletons=[skeleton])
    labels.update()
    path = predictions_dir / f"scan_{scan_id}.{model}.root_{root_type}.slp"
    sio.save_slp(labels, str(path), embed=False)
    return path


def build_inputs(
    tmp_path: Path,
    rows=None,
    populate_images: bool = True,
    predictions: tuple = (("primary", 6), ("lateral", 4)),
    scans=SCANS,
) -> tuple[Path, Path, Path, Path]:
    """Stage a manifest, curated images, and predictions; return the four build paths."""
    manifest_csv = tmp_path / "sample_manifest.csv"
    rows = write_manifest(manifest_csv, rows if rows is not None else manifest_rows())

    images_dir = tmp_path / "package/images"
    images_dir.mkdir(parents=True)
    if populate_images:
        for row in rows:
            write_jpeg(images_dir / row["output_filename"])

    predictions_dir = tmp_path / "sleap_roots_traits_input"
    predictions_dir.mkdir(parents=True)
    for scan_id, *_ in scans:
        for root_type, node_count in predictions:
            write_predictions(
                predictions_dir, scan_id, root_type, node_count=node_count
            )

    output_dir = tmp_path / "package"
    return manifest_csv, images_dir, predictions_dir, output_dir


def build(tmp_path: Path, **kwargs) -> Path:
    """Run a build over the standard fixture and return the output directory."""
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, **kwargs
    )
    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)
    return output_dir


def primary(output_dir: Path) -> sio.Labels:
    """Load the built primary project."""
    return sio.load_slp(str(output_dir / "soybean_weep_primary_labels.v000.slp"))


# --------------------------------------------------------------------------------------
# Characterization — behavior the port inherited unchanged
# --------------------------------------------------------------------------------------


def test_writes_both_root_type_projects_under_versioned_names(tmp_path):
    output_dir = build(tmp_path)

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
    labels = primary(build(tmp_path))

    assert len(labels.videos) == 2
    for video in labels.videos:
        assert len(video.filename) == 3


def test_frames_land_at_their_within_scan_position_carrying_the_predictions(tmp_path):
    labels = primary(build(tmp_path))

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
    labels = primary(build(tmp_path))

    by_position = {}
    for lf in labels.labeled_frames:
        by_position.setdefault(lf.frame_idx, set()).add(
            float(lf.instances[0].points[0]["xy"][0])
        )
    assert by_position == {0: {1.0}, 1: {25.0}, 2: {49.0}}


def test_instances_are_rebuilt_against_one_canonical_skeleton(tmp_path):
    """Aggregating N prediction files must not leave N duplicate skeletons behind."""
    labels = primary(build(tmp_path))

    assert len(labels.skeletons) == 1
    assert all(
        lf.instances[0].skeleton is labels.skeletons[0] for lf in labels.labeled_frames
    )


def test_the_hardcoded_soybean_skeletons_are_what_gets_written(tmp_path):
    """Pins Decision 7's starting point: one crop, hand-edited per crop, 6 and 4 nodes."""
    output_dir = build(tmp_path)

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


def test_a_scan_predicted_for_one_root_type_only_appears_in_that_project(tmp_path):
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_2.*.root_lateral.slp"):
        path.unlink()

    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)

    lateral = sio.load_slp(str(output_dir / "soybean_weep_lateral_labels.v000.slp"))
    assert len(primary(output_dir).videos) == 2
    assert len(lateral.videos) == 1


def test_multiple_prediction_files_for_a_scan_warn_and_use_the_first(tmp_path, caplog):
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    write_predictions(predictions_dir, 1, "primary", model="model_b")

    with caplog.at_level("WARNING"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )

    assert "Multiple primary predictions for scan 1" in caplog.text


def test_the_saved_project_references_external_images(tmp_path):
    """Pins ``embed=False`` — the behavior section 5 changes on purpose.

    This is the state design.md indicts: six of the eight published collections carry
    ``repaired_from: "v0"`` because a reference like this broke and was hand-patched into
    a package afterwards, permanently capping the label set. Task 5.1's test is the one
    that must fail against this commit.
    """
    output_dir = build(tmp_path)
    labels = primary(output_dir)

    referenced = Path(labels.videos[0].filename[0])
    assert referenced.parent == (output_dir / "images")
    assert referenced.is_file()


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

    Distinct from a scan predicted for only one root type, which stays legitimate — a
    model finding no laterals is a result, whereas a scan absent from every prediction
    file means the selection cannot be honored.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    for path in predictions_dir.glob("scan_2.*"):
        path.unlink()

    with pytest.raises(ValueError, match="no predictions"):
        build_slp_project(
            manifest_csv, images_dir, predictions_dir, output_dir, METADATA
        )


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
        species="soybean", mode="cylinder", root_types=("primary",)
    )

    written = build_slp_project(
        manifest_csv, images_dir, predictions_dir, output_dir, metadata
    )

    assert set(written) == {"primary"}
    assert not (output_dir / "soybean_weep_lateral_labels.v000.slp").exists()


def test_a_species_without_a_skeleton_fails_before_reading_anything(tmp_path):
    """Metadata is checked first, so a wrong species is not reported as a data problem.

    The builder still carries the vault script's hardcoded soybean pair; giving another
    species soybean's node counts would produce a package that looks fine and cannot be
    combined with anything. Section 6's committed table is what lifts this.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, populate_images=False
    )
    metadata = PackageMetadata(species="rice", mode="cylinder", root_types=("primary",))

    with pytest.raises(NotImplementedError, match="rice"):
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
    assert Path(labels.videos[0].filename[0]).name.endswith("_age3_0.jpg")


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
