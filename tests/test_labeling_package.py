"""Task 8.4 — assembling a complete package, all-or-nothing.

The four stages each fail loudly on their own (sections 2–6), but a package is only a
package once all of them have run and agreed. This is where they are run in order, and
where the spec's "the output directory contains the `.slp` file, `sample_manifest.csv`,
and the package metadata, and no required piece is left in a temporary or user-specific
location" becomes a property rather than a description.

The all-or-nothing rule is the same one task 4.7 applies inside the builder, raised a
level: the destination directory does not exist until a validated package is ready to be
moved into it. A half-built package that a later step could mistake for a complete one is
the F1 failure this change exists to make impossible, and "the build crashed partway" is
just as good a way to produce one as "the build ignored an empty selection".
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest
import sleap_io as sio

from conftest import write_jpeg
from test_labeling_build_package import (
    METADATA,
    SCANS,
    manifest_rows,
    write_manifest,
    write_predictions,
)
from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.metadata import (
    PACKAGE_METADATA_FILENAME,
    SelectionParameters,
    read_package_metadata,
)
from sleap_roots_training.labeling.package import build_labeling_package
from sleap_roots_training.labeling.validate import validate_package

TOTAL_VIEWS = 72
ACCESSIONS = {"12742739": "A3244", "12742740": "WEEP-1-4"}
SELECTION = SelectionParameters(
    seed=42, plants_per_group=5, views_per_plant=3, total_views=TOTAL_VIEWS
)


def download(tmp_path: Path, rows=None):
    """Materialize a Bloom download, a manifest, and the pipeline's predictions.

    The source images live where ``scans.csv`` says they do — the copy step resolves
    against that file's directory (task 7.2) — so this exercises the real resolution rule
    rather than handing the assembler a pre-populated ``images/``.
    """
    rows = list(rows if rows is not None else manifest_rows())
    download_dir = tmp_path / "WEEP_soybean/images_downloader_output"
    download_dir.mkdir(parents=True)

    with (download_dir / "scans.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["scan_id", "plant_qr_code", "scan_path"])
        for scan_id, qr, age, *_ in SCANS:
            scan_path = f"images/Wave1/Day{age}_20250101/{qr}"
            writer.writerow([scan_id, qr, scan_path])
            for view in range(1, TOTAL_VIEWS + 1):
                write_jpeg(download_dir / scan_path / f"{view}.jpg")

    manifest_csv = write_manifest(tmp_path / "sample_manifest.csv", rows) and (
        tmp_path / "sample_manifest.csv"
    )
    predictions_dir = tmp_path / "sleap_roots_traits_input"
    predictions_dir.mkdir()
    for scan_id, *_ in SCANS:
        write_predictions(predictions_dir, scan_id, "primary", node_count=6)
        write_predictions(predictions_dir, scan_id, "lateral", node_count=4)
    return manifest_csv, download_dir / "scans.csv", predictions_dir


def build(tmp_path: Path, rows=None, output_dir=None, **overrides):
    """Assemble a package over the standard fixture and return its directory."""
    manifest_csv, scans_csv, predictions_dir = download(tmp_path, rows=rows)
    kwargs = {
        "metadata": METADATA,
        "bloom_experiment_id": 10102496,
        "accessions": ACCESSIONS,
        "selection": SELECTION,
    }
    kwargs.update(overrides)
    return build_labeling_package(
        manifest_csv,
        scans_csv,
        predictions_dir,
        output_dir or tmp_path / "soybean-weep-labeling",
        **kwargs,
    )


def test_a_successful_build_writes_the_whole_layout(tmp_path):
    package_dir = build(tmp_path)

    assert (package_dir / "sample_manifest.csv").is_file()
    assert (package_dir / PACKAGE_METADATA_FILENAME).is_file()
    assert (package_dir / "README.md").is_file()
    assert (package_dir / "images").is_dir()
    assert (package_dir / "soybean_weep_primary_labels.v000.slp").is_file()
    assert (package_dir / "soybean_weep_lateral_labels.v000.slp").is_file()


def test_the_built_package_validates(tmp_path):
    """The assembler and the validator agree, so neither is only asserted by its author."""
    package_dir = build(tmp_path)

    assert validate_package(package_dir).frame_count == 6


def test_the_curated_images_are_the_manifest_rows(tmp_path):
    package_dir = build(tmp_path)

    names = {p.name for p in (package_dir / "images").glob("*.jpg")}
    rows = list(csv.DictReader((package_dir / "sample_manifest.csv").open()))
    assert names == {row["output_filename"] for row in rows}


def test_the_record_carries_the_selection_parameters_it_was_built_with(tmp_path):
    """Decision 5: the package, not the shell history, is where the seed lives."""
    package_dir = build(
        tmp_path,
        selection=SelectionParameters(
            seed=7, plants_per_group=2, views_per_plant=3, total_views=TOTAL_VIEWS
        ),
    )

    selection = read_package_metadata(package_dir).selection
    assert (selection.seed, selection.plants_per_group) == (7, 2)


def test_the_recorded_skeletons_are_the_ones_written_into_the_slp(tmp_path):
    package_dir = build(tmp_path)

    record = read_package_metadata(package_dir)
    for root_type in ("primary", "lateral"):
        labels = sio.load_slp(
            str(package_dir / f"soybean_weep_{root_type}_labels.v000.slp"),
            open_videos=False,
        )
        assert record.skeletons[root_type] == tuple(labels.skeletons[0].node_names)


def test_the_package_is_self_contained_once_the_download_is_gone(tmp_path):
    """The delivery property, end to end rather than at the builder alone."""
    package_dir = build(tmp_path)
    shutil.rmtree(tmp_path / "WEEP_soybean")

    labels = sio.load_slp(str(package_dir / "soybean_weep_primary_labels.v000.slp"))

    assert labels.labeled_frames[0].image.shape[0] > 0


# --------------------------------------------------------------------------------------
# All-or-nothing
# --------------------------------------------------------------------------------------


def test_a_failed_build_writes_no_package_directory(tmp_path):
    """Task 4.7's rule, raised to the package.

    A scan with no predictions fails the build. What matters here is not the failure —
    that is section 4's — but that the destination is not left behind for a later step to
    mistake for a complete package.
    """
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    for path in predictions_dir.glob("scan_2.*"):
        path.unlink()
    output_dir = tmp_path / "soybean-weep-labeling"

    with pytest.raises(ValueError):
        build_labeling_package(
            manifest_csv,
            scans_csv,
            predictions_dir,
            output_dir,
            metadata=METADATA,
            bloom_experiment_id=10102496,
            accessions=ACCESSIONS,
            selection=SELECTION,
        )

    assert not output_dir.exists()


def test_a_failed_build_leaves_no_staging_directory_behind(tmp_path):
    """Assembling elsewhere and moving is only all-or-nothing if the elsewhere is cleaned."""
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    for path in predictions_dir.glob("scan_2.*"):
        path.unlink()
    destination = tmp_path / "out/soybean-weep-labeling"
    destination.parent.mkdir()

    with pytest.raises(ValueError):
        build_labeling_package(
            manifest_csv,
            scans_csv,
            predictions_dir,
            destination,
            metadata=METADATA,
            bloom_experiment_id=10102496,
            accessions=ACCESSIONS,
            selection=SELECTION,
        )

    assert list(destination.parent.iterdir()) == []


def test_an_existing_destination_is_refused_rather_than_merged(tmp_path):
    """A rebuild over a previous package would leave the older run's files in place.

    ``v000`` is immutable by the versioning convention the README documents, so silently
    merging into an existing directory produces a package that is partly two builds.
    """
    output_dir = tmp_path / "soybean-weep-labeling"
    output_dir.mkdir()
    (output_dir / "leftover.txt").write_text("from an earlier run")

    with pytest.raises(ValueError, match="(?i)exists"):
        build(tmp_path, output_dir=output_dir)

    assert (output_dir / "leftover.txt").is_file()


def test_selection_parameters_that_cannot_have_produced_the_manifest_are_refused(
    tmp_path,
):
    """The parameters are passed again at build time, so they can be passed wrongly.

    Recording a seed that did not produce the package is worse than recording none: it
    invites a re-derivation that silently yields a different label set, which is exactly
    what Decision 5 exists to prevent. The manifest cannot confirm the seed, but it can
    contradict ``views_per_plant``.
    """
    with pytest.raises(ValueError, match="views_per_plant"):
        build(
            tmp_path,
            selection=SelectionParameters(
                seed=42, plants_per_group=5, views_per_plant=2, total_views=TOTAL_VIEWS
            ),
        )


def test_a_manifest_missing_a_required_column_fails_before_anything_is_copied(tmp_path):
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    rows = list(csv.DictReader(manifest_csv.open()))
    remaining = [c for c in ss.MANIFEST_COLUMNS if c != "accession_name"]
    with manifest_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=remaining, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    output_dir = tmp_path / "soybean-weep-labeling"

    with pytest.raises(ValueError, match="accession_name"):
        build_labeling_package(
            manifest_csv,
            scans_csv,
            predictions_dir,
            output_dir,
            metadata=METADATA,
            bloom_experiment_id=10102496,
            accessions=ACCESSIONS,
            selection=SELECTION,
        )

    assert not output_dir.exists()
