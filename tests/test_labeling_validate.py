"""Tasks 8.1/8.2 — the check that runs before a package is published.

design.md Decision 3 makes the package directory a named contract: this change writes it,
``#10``'s ``publish-labels`` reads it. An implicit layout would make that seam the place the
two disagree, so the layout, the manifest's columns, and the counts are all checked here,
and every rejection names the offending piece rather than reporting that "validation
failed".

The packages under test are **hand-assembled**, not produced by the CLI. That is
deliberate, and it is the same reason the self-containment check exists in
``test_labeling_embed.py``: the guarantee has to be a property of the *package*, so that a
package built by an older tool or patched together by a person is judged by the same rule
as one this repo just wrote. A validator that only ever sees its own builder's output
tests agreement, not correctness.
"""

from __future__ import annotations

import csv
import shutil

import pytest
import sleap_io as sio

from conftest import (
    FRAME_COUNT,
    METADATA,
    SKELETONS,
    build_inputs,
    complete_package,
    manifest_rows,
    package_record,
    write_jpeg,
    write_manifest,
)
from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.build_package import build_slp_project
from sleap_roots_training.labeling.metadata import (
    PACKAGE_METADATA_FILENAME,
    PackageRecord,
    SelectionParameters,
    write_package_metadata,
)
from sleap_roots_training.labeling.validate import validate_package


def test_a_complete_package_validates(tmp_path):
    """The positive control. Without it, every rejection below could pass vacuously."""
    package_dir = complete_package(tmp_path)

    record = validate_package(package_dir)

    assert record.frame_count == FRAME_COUNT
    assert record.metadata.species == "soybean"


def test_a_missing_manifest_is_named(tmp_path):
    package_dir = complete_package(tmp_path)
    (package_dir / "sample_manifest.csv").unlink()

    with pytest.raises(ValueError, match="sample_manifest.csv"):
        validate_package(package_dir)


def test_a_missing_metadata_file_is_named(tmp_path):
    package_dir = complete_package(tmp_path)
    (package_dir / PACKAGE_METADATA_FILENAME).unlink()

    with pytest.raises(FileNotFoundError, match=PACKAGE_METADATA_FILENAME):
        validate_package(package_dir)


def test_a_missing_images_directory_is_named(tmp_path):
    """5.5 keeps ``images/`` in the package, so its absence is a layout failure."""
    package_dir = complete_package(tmp_path)
    shutil.rmtree(package_dir / "images")

    with pytest.raises(ValueError, match="images"):
        validate_package(package_dir)


def test_a_missing_project_file_names_the_root_type_and_the_filename(tmp_path):
    package_dir = complete_package(tmp_path)
    (package_dir / "soybean_weep_lateral_labels.v000.slp").unlink()

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    assert "lateral" in str(excinfo.value)
    assert "soybean_weep_lateral_labels.v000.slp" in str(excinfo.value)


def test_a_directory_that_is_not_a_package_is_rejected(tmp_path):
    empty = tmp_path / "not-a-package"
    empty.mkdir()

    with pytest.raises(FileNotFoundError, match=PACKAGE_METADATA_FILENAME):
        validate_package(empty)


@pytest.mark.parametrize("column", ["scan_id", "accession_name", "output_filename"])
def test_a_manifest_missing_a_required_column_names_it(tmp_path, column):
    """Decision 3 enumerates the columns, so a package short one is not publishable.

    The row-level provenance travelling inside the artifact is the whole point — it is
    what lets a consumer recover the scans and accessions without the source filesystem.
    """
    package_dir = complete_package(tmp_path)
    manifest = package_dir / "sample_manifest.csv"
    rows = list(csv.DictReader(manifest.open()))
    remaining = [c for c in ss.MANIFEST_COLUMNS if c != column]
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=remaining, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match=column):
        validate_package(package_dir)


def test_a_declared_frame_count_that_disagrees_reports_both_numbers(tmp_path):
    package_dir = complete_package(tmp_path, record=package_record(frame_count=99))

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    message = str(excinfo.value)
    assert "99" in message and str(FRAME_COUNT) in message


def test_a_project_shorter_than_the_declared_count_is_rejected(tmp_path):
    """RED against the port: ``frame_count`` was only ever compared against itself.

    The builder set ``frame_count=len(manifest)`` and the count check compared it against
    the manifest *that same builder copied into the package* — the same number on both
    sides, so for any builder-produced package it could never fail no matter how short the
    ``.slp`` files were. Nothing in validation opened the projects to count frames.

    A short project is the on-disk signature of frames dropped during the build, which are
    the frames the model failed on. The package is hand-shortened here for the reason the
    module docstring gives: the guarantee has to hold for a package built by an older tool
    or assembled by a person, not only for one this repo just wrote.
    """
    package_dir = complete_package(tmp_path)
    lateral = package_dir / "soybean_weep_lateral_labels.v000.slp"
    labels = sio.load_slp(str(lateral))
    labels.labeled_frames = labels.labeled_frames[:-1]
    labels.update()
    # Written beside the original and moved into place: re-embedding reads the frames back
    # out of the file being replaced, so saving over it in place cannot work.
    shortened = lateral.with_name("shortened.slp")
    sio.save_slp(labels, str(shortened), embed=True, verbose=False)
    shortened.replace(lateral)

    with pytest.raises(ValueError, match="labeled frame") as excinfo:
        validate_package(package_dir)

    message = str(excinfo.value)
    assert str(FRAME_COUNT) in message and str(FRAME_COUNT - 1) in message
    assert "lateral" in message


def test_a_complete_package_still_validates_after_the_frame_count_check(tmp_path):
    # The positive control for the check above: it must not reject a correct package,
    # where every declared root type's project carries one frame per manifest row.
    package_dir = complete_package(tmp_path)

    record = validate_package(package_dir)

    for root_type in record.metadata.root_types:
        labels = sio.load_slp(
            str(package_dir / f"soybean_weep_{root_type}_labels.v000.slp")
        )
        assert len(labels.labeled_frames) == record.frame_count


def test_a_curated_image_count_that_disagrees_reports_both_numbers(tmp_path):
    """The mismatch the README reported only as prose (F7), now an error.

    ``generate_readme.py`` globbed ``images/*.jpg`` for its count while the manifest was
    the record of what should be there, so a dropped image showed up as a smaller number
    in the documentation and nowhere else.
    """
    package_dir = complete_package(tmp_path)
    dropped = sorted((package_dir / "images").glob("*.jpg"))[0]
    dropped.unlink()

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    # The file, not just the two numbers: naming it is what makes the error actionable.
    assert dropped.name in str(excinfo.value)


def test_an_extra_curated_image_is_also_a_mismatch(tmp_path):
    """One-to-one runs both ways: an image no manifest row claims is unexplained data."""
    package_dir = complete_package(tmp_path)
    write_jpeg(package_dir / "images" / "not_in_the_manifest.jpg")

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    # This branch was unreachable while the cardinality check ran first: an unclaimed file
    # always changes the count too, so the less useful of the two errors always won.
    assert "not_in_the_manifest.jpg" in str(excinfo.value)


@pytest.mark.parametrize(
    "sidecar", [".DS_Store", "Thumbs.db", "desktop.ini", "._A3244_9DK8KJJEZR.jpg"]
)
def test_an_operating_system_sidecar_does_not_fail_a_valid_package(tmp_path, sidecar):
    """RED against the port: one Finder visit rejected a correct package.

    Packages ship over Box and are opened on macOS, so a ``.DS_Store`` in ``images/`` is
    routine. It used to fail validation with "images/ holds 7 file(s) but
    sample_manifest.csv has 6 row(s)" — blaming the manifest for a file it has nothing to
    do with. ``tests/test_registry_models.py`` already filters these names for the same
    reason.
    """
    package_dir = complete_package(tmp_path)
    (package_dir / "images" / sidecar).write_bytes(b"\x00")

    assert validate_package(package_dir).frame_count == FRAME_COUNT


def test_a_manifest_row_whose_image_is_absent_is_named(tmp_path):
    """A count check alone would pass if one image were dropped and another added."""
    package_dir = complete_package(tmp_path)
    dropped = sorted((package_dir / "images").glob("*.jpg"))[0]
    dropped.unlink()
    write_jpeg(package_dir / "images" / "not_in_the_manifest.jpg")

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    assert dropped.name in str(excinfo.value)


def test_a_duplicate_output_filename_names_the_colliding_rows(tmp_path):
    """The same rule 2.9 enforces at selection and 3.5 enforces at the copy step.

    Enforced here too because a hand-edited manifest is exactly what this validator is
    for: two scans drawn from one image, with every count still reading correct.
    """
    rows = list(manifest_rows())
    rows[1]["output_filename"] = rows[0]["output_filename"]
    package_dir = complete_package(tmp_path, rows=rows)

    with pytest.raises(ValueError, match="output_filename"):
        validate_package(package_dir)


def test_a_package_whose_slp_is_not_self_contained_is_rejected(tmp_path):
    """Task 5.3's guarantee, reached through the single entry point ``#10`` calls."""
    package_dir = complete_package(tmp_path)
    path = package_dir / "soybean_weep_primary_labels.v000.slp"
    labels = sio.load_slp(str(path))
    path.unlink()
    sio.save_slp(labels, str(path), embed=False)

    with pytest.raises(ValueError, match="not self-contained"):
        validate_package(package_dir)


def test_a_recorded_skeleton_that_disagrees_with_the_slp_is_rejected(tmp_path):
    """Task 8.3c's drift, caught where it can be caught.

    The node counts lived twice — as prose in ``generate_readme.py:58-60`` and as
    constants in ``build_slp_project.py:43-58`` — and nothing compared them. Now the
    record is the single source the README renders from, so the check that matters is
    that the record agrees with the ``.slp`` actually written.
    """
    wrong = dict(SKELETONS, lateral=("r1", "r2", "r3"))
    package_dir = complete_package(tmp_path, record=package_record(skeletons=wrong))

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    message = str(excinfo.value)
    assert "lateral" in message
    assert "r4" in message


def test_validation_reads_nothing_outside_the_package(tmp_path):
    """ "No dependency on the machine that produced it" (Decision 3), made checkable.

    The fixture's manifest names source scan paths that never existed on this machine.
    Validation passing with them unreachable is the property; a validator that resolved
    ``source_image`` would make a valid package fail everywhere except where it was built.
    """
    package_dir = complete_package(tmp_path)
    moved = tmp_path / "delivered" / "soybean-weep-labeling"
    moved.parent.mkdir()
    shutil.move(str(package_dir), str(moved))

    assert validate_package(moved).frame_count == FRAME_COUNT


def test_an_empty_manifest_is_rejected(tmp_path):
    """F1's silent-empty package, judged at the artifact rather than at the build."""
    package_dir = complete_package(tmp_path)
    write_manifest(package_dir / "sample_manifest.csv", [])
    for image in (package_dir / "images").glob("*.jpg"):
        image.unlink()

    with pytest.raises(ValueError, match="(?i)no rows|empty"):
        validate_package(package_dir)
