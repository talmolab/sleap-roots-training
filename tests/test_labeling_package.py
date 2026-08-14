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
from unittest import mock

import pytest
import sleap_io as sio

from conftest import (
    ACCESSIONS,
    METADATA,
    SCANS,
    SELECTION,
    TOTAL_VIEWS,
    build_package_dir,
    download,
    manifest_rows,
    write_predictions,
)
from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.metadata import (
    PACKAGE_METADATA_FILENAME,
    SelectionParameters,
    read_package_metadata,
)
from sleap_roots_training.labeling import package as package_module
from sleap_roots_training.labeling.package import build_labeling_package
from sleap_roots_training.labeling.validate import validate_package


def test_a_successful_build_writes_the_whole_layout(tmp_path):
    package_dir = build_package_dir(tmp_path)

    assert (package_dir / "sample_manifest.csv").is_file()
    assert (package_dir / PACKAGE_METADATA_FILENAME).is_file()
    assert (package_dir / "README.md").is_file()
    assert (package_dir / "images").is_dir()
    assert (package_dir / "soybean_weep_primary_labels.v000.slp").is_file()
    assert (package_dir / "soybean_weep_lateral_labels.v000.slp").is_file()


def test_the_built_package_validates(tmp_path):
    """The assembler and the validator agree, so neither is only asserted by its author."""
    package_dir = build_package_dir(tmp_path)

    assert validate_package(package_dir).frame_count == 6


def test_the_curated_images_are_the_manifest_rows(tmp_path):
    package_dir = build_package_dir(tmp_path)

    names = {p.name for p in (package_dir / "images").glob("*.jpg")}
    rows = list(csv.DictReader((package_dir / "sample_manifest.csv").open()))
    assert names == {row["output_filename"] for row in rows}


def test_the_record_carries_the_selection_parameters_it_was_built_with(tmp_path):
    """Decision 5: the package, not the shell history, is where the seed lives."""
    package_dir = build_package_dir(
        tmp_path,
        selection=SelectionParameters(
            seed=7, plants_per_group=2, views_per_plant=3, total_views=TOTAL_VIEWS
        ),
    )

    selection = read_package_metadata(package_dir).selection
    assert (selection.seed, selection.plants_per_group) == (7, 2)


def test_the_recorded_skeletons_are_the_ones_written_into_the_slp(tmp_path):
    package_dir = build_package_dir(tmp_path)

    record = read_package_metadata(package_dir)
    for root_type in ("primary", "lateral"):
        labels = sio.load_slp(
            str(package_dir / f"soybean_weep_{root_type}_labels.v000.slp"),
            open_videos=False,
        )
        assert record.skeletons[root_type] == tuple(labels.skeletons[0].node_names)


def test_the_package_is_self_contained_once_the_download_is_gone(tmp_path):
    """The delivery property, end to end rather than at the builder alone."""
    package_dir = build_package_dir(tmp_path)
    shutil.rmtree(tmp_path / "WEEP_soybean")

    labels = sio.load_slp(str(package_dir / "soybean_weep_primary_labels.v000.slp"))

    assert labels.labeled_frames[0].image.shape[0] > 0


# --------------------------------------------------------------------------------------
# All-or-nothing
# --------------------------------------------------------------------------------------


def test_a_manifest_that_was_empty_from_the_start_is_refused_by_name(tmp_path):
    """The third way into an empty package, and the one that stayed accidental.

    Selection and the copy step were both made to reject an empty selection, but neither
    guards this entry: a manifest handed straight to `build_labeling_package` -- reused
    from an earlier run, hand-written, or produced by a tool that is not this selector.
    The orchestrator ran `_assert_selection_could_have_produced` before reaching
    `build_slp_project`'s own good check, and `int(per_plant.max())` on an empty Series
    raised `cannot convert float NaN to integer`: a real refusal reached by accident,
    reported as a numpy message that names nothing an operator can act on.

    Surfaced by the CLI-chain test this review suggested, which is exactly the seam a
    per-stage test could not see -- both stages were individually correct.
    """
    _, scans_csv, predictions_dir = download(tmp_path)
    empty_csv = tmp_path / "empty_manifest.csv"
    with empty_csv.open("w", newline="") as fh:
        csv.writer(fh).writerow(list(ss.MANIFEST_COLUMNS))
    output_dir = tmp_path / "soybean-weep-labeling"

    with pytest.raises(ValueError) as excinfo:
        build_labeling_package(
            empty_csv,
            scans_csv,
            predictions_dir,
            output_dir,
            METADATA,
            bloom_experiment_id=10102496,
            accessions=ACCESSIONS,
            selection=SELECTION,
        )

    message = str(excinfo.value)
    assert "no rows" in message
    assert empty_csv.name in message
    assert "NaN" not in message
    assert not output_dir.exists()


@pytest.mark.parametrize("column", ["scan_id", "frame_index", "output_filename"])
def test_a_manifest_missing_a_column_names_it_instead_of_raising_key_error(
    tmp_path, column
):
    """The orchestrator validated no columns of its own, and indexed one immediately.

    Second-order effect of the ordering fix above, pinned because it is a different
    failure from the empty one and would otherwise be incidental. The first thing this
    stage did with a manifest was `groupby("scan_id")`, so a renamed or dropped column
    escaped as a bare `KeyError: 'scan_id'` -- which `cli.py`'s `except (OSError,
    ValueError)` does not catch, so the operator got the traceback that `_labeling_error`
    exists to prevent. Every *other* stage validated its columns at its entrance; this one
    inherited the check only once `assert_buildable_manifest` was hoisted ahead of the
    selection cross-check.
    """
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    rows = list(csv.DictReader(manifest_csv.open()))
    remaining = [c for c in ss.MANIFEST_COLUMNS if c != column]
    with manifest_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=remaining, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    output_dir = tmp_path / "soybean-weep-labeling"

    with pytest.raises(ValueError) as excinfo:
        build_labeling_package(
            manifest_csv,
            scans_csv,
            predictions_dir,
            output_dir,
            METADATA,
            bloom_experiment_id=10102496,
            accessions=ACCESSIONS,
            selection=SELECTION,
        )

    message = str(excinfo.value)
    assert "missing required column" in message
    assert column in message
    assert not output_dir.exists()


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
        build_package_dir(tmp_path, output_dir=output_dir)

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
        build_package_dir(
            tmp_path,
            selection=SelectionParameters(
                seed=42, plants_per_group=5, views_per_plant=2, total_views=TOTAL_VIEWS
            ),
        )


def test_a_plant_scanned_at_two_ages_builds_at_its_own_selection_parameters(tmp_path):
    """RED against the port, which rejected its own selector's output.

    The invariant was grouped by ``plant_qr_code``, but selection emits
    ``views_per_plant`` rows per *scan* and filters on barcode alone — so a plant scanned
    at two ages legitimately carries twice that many rows, and every longitudinal
    experiment failed here with "these parameters did not produce this manifest" when they
    had. Longitudinal is the normal shape of this data: it is why ``output_filename``
    embeds the age, why ``assert_unique_output_filenames`` keys uniqueness on the
    (barcode, age) pair, and why ``--cleaned-csv`` takes a glob over per-age QC files.
    """
    rows = [dict(row) for row in manifest_rows()]
    for row in list(rows):
        if row["scan_id"] == 1:
            later = dict(row)
            later["scan_id"] = 99
            later["plant_age_days"] = 5
            later["output_filename"] = later["output_filename"].replace("age3", "age5")
            later["source_scan_path"] = later["source_scan_path"].replace(
                "Day3", "Day5"
            )
            later["source_image"] = later["source_image"].replace("Day3", "Day5")
            rows.append(later)
    scans = SCANS + ((99, "9DK8KJJEZR", 5, 12742739, "A3244"),)

    package_dir = build_package_dir(tmp_path, rows=rows, scans=scans)

    record = validate_package(package_dir)
    assert record.frame_count == len(rows)
    # Six rows for one barcode, three per scan — the parameters that produced it.
    assert record.selection.views_per_plant == 3


def test_a_scan_carrying_more_views_than_the_parameters_allow_is_still_refused(
    tmp_path,
):
    # The invariant moved from plant to scan, not away: a single scan with more views than
    # `views_per_plant` still means the recorded parameters did not produce this manifest.
    with pytest.raises(ValueError, match="views to a single scan"):
        build_package_dir(
            tmp_path,
            selection=SelectionParameters(
                seed=42, plants_per_group=5, views_per_plant=2, total_views=TOTAL_VIEWS
            ),
        )


def test_a_package_whose_model_found_nothing_in_some_frames_builds_and_validates(
    tmp_path,
):
    """The builder and the validator now count at the same granularity.

    They did not: the builder tracked contribution per *scan* while
    ``assert_project_holds_every_declared_frame`` counts per *frame*, so a scan whose model
    found laterals in only one of its three views passed the build and then failed
    validation — inside ``build_labeling_package``, after the whole staging directory had
    been assembled, with a message blaming the model for what may be a plant with no
    lateral roots. Writing an empty frame for a genuine absence makes both checks "one
    frame per manifest row, per declared root type".
    """
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    # Scan 1's laterals: the model looked at all three views and found nothing.
    for path in predictions_dir.glob("scan_1.*.root_lateral.slp"):
        path.unlink()
    write_predictions(predictions_dir, 1, "lateral", node_count=4, all_nan=True)

    package_dir = build_labeling_package(
        manifest_csv,
        scans_csv,
        predictions_dir,
        tmp_path / "soybean-weep-labeling",
        metadata=METADATA,
        bloom_experiment_id=10102496,
        accessions=ACCESSIONS,
        selection=SELECTION,
    )

    record = validate_package(package_dir)
    lateral = sio.load_slp(str(package_dir / "soybean_weep_lateral_labels.v000.slp"))
    assert len(lateral.labeled_frames) == record.frame_count
    assert sum(1 for lf in lateral.labeled_frames if not lf.instances) == 3
    # The absence is confirmable: the labeler can open the frame and see the image.
    blank = next(lf for lf in lateral.labeled_frames if not lf.instances)
    assert blank.image.shape[0] > 0


def test_a_built_package_records_its_provenance(tmp_path):
    """The block is optional on read but must always be populated on the publish path.

    That asymmetry — optional in the contract, guaranteed by the builder — is the part most
    likely to regress silently, since a package with no provenance still validates.
    """
    package_dir = build_package_dir(tmp_path)

    provenance = read_package_metadata(package_dir).provenance

    assert provenance is not None
    assert len(provenance.scans_csv_sha256) == 64
    assert len(provenance.manifest_sha256) == 64
    assert len(provenance.skeleton_table_sha256) == 64
    assert provenance.code_version
    # Which model produced the starting points a labeler will anchor on.
    assert provenance.prediction_models == ("model_a",)


def test_a_destination_that_appears_mid_build_is_not_absorbed(tmp_path):
    """The TOCTOU window between the up-front check and the move.

    ``Path.rename`` replaces an empty destination directory silently on POSIX, so a second
    run that created the directory while this one was building would have its output
    absorbed without a word. A package version is an immutable snapshot, so the check is
    made again at the moment of the move rather than trusted from the start of the build.
    """
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    output_dir = tmp_path / "soybean-weep-labeling"
    real_render = package_module.render_readme

    def render_then_race(staging):
        # The last thing before validation and the move: stands in for another run
        # creating the destination while this build was working.
        result = real_render(staging)
        output_dir.mkdir(parents=True, exist_ok=True)
        return result

    with mock.patch.object(package_module, "render_readme", render_then_race):
        with pytest.raises(
            ValueError, match="appeared while this package was being built"
        ):
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

    # The destination is left exactly as the other run had it, and staging is cleaned up.
    assert list(output_dir.iterdir()) == []
    assert not list(tmp_path.glob("*.partial-*"))


def test_a_staging_directory_that_cannot_be_removed_is_reported(tmp_path, caplog):
    """``ignore_errors=True`` alone swallowed this with no log line.

    On Windows a still-open ``.slp`` handle is enough. The bytes stay on disk either way;
    what changes is whether anyone finds out.
    """
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    for path in predictions_dir.glob("scan_2.*"):
        path.unlink()

    with mock.patch.object(package_module.shutil, "rmtree", lambda *a, **k: None):
        with caplog.at_level("ERROR"):
            with pytest.raises(ValueError):
                build_labeling_package(
                    manifest_csv,
                    scans_csv,
                    predictions_dir,
                    tmp_path / "soybean-weep-labeling",
                    metadata=METADATA,
                    bloom_experiment_id=10102496,
                    accessions=ACCESSIONS,
                    selection=SELECTION,
                )

    assert "Could not remove the staging directory" in caplog.text
    assert "remove it by hand" in caplog.text


def test_an_unreadable_source_scan_fails_the_build_and_names_the_path(tmp_path):
    """The spec scenario of the same name, which had no test at the level it describes.

    ``test_labeling_copy_images.py`` covers the copy step in isolation; this is the
    orchestrated build, where the spec's "no package directory is written" is the part that
    matters — a failure here must leave nothing a later step could mistake for a package.
    """
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    shutil.rmtree(scans_csv.parent / "images/Wave1/Day3_20250101/8XQ2LMNPQR")
    output_dir = tmp_path / "soybean-weep-labeling"

    with pytest.raises(FileNotFoundError, match="8XQ2LMNPQR") as excinfo:
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

    assert "8XQ2LMNPQR" in str(excinfo.value)
    assert not output_dir.exists()
    # And no staging directory survives to be found later.
    assert not list(tmp_path.glob("*.partial-*"))


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
