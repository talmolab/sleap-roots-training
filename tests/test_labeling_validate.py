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

from conftest import write_jpeg
from test_labeling_build_package import (
    METADATA,
    build_inputs,
    manifest_rows,
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

#: The fixture's two scans x three views.
FRAME_COUNT = 6

SKELETONS = {
    "primary": ("r1", "r2", "r3", "r4", "r5", "r6"),
    "lateral": ("r1", "r2", "r3", "r4"),
}


def package_record(**overrides) -> PackageRecord:
    """Build the record describing the fixture package, stating only the deviation."""
    fields = {
        "metadata": METADATA,
        "bloom_experiment_id": 10102496,
        "accessions": {"12742739": "A3244", "12742740": "WEEP-1-4"},
        "selection": SelectionParameters(
            seed=42, plants_per_group=5, views_per_plant=3, total_views=72
        ),
        "frame_count": FRAME_COUNT,
        "skeletons": SKELETONS,
        "version": "v000",
    }
    fields.update(overrides)
    return PackageRecord(**fields)


def complete_package(tmp_path, rows=None, record=None):
    """Hand-assemble a package that passes: images, manifest, projects, metadata.

    Mirrors what a correct build produces without going through one, so a validation test
    that fails is a statement about the validator rather than about the builder.
    """
    manifest_csv, images_dir, predictions_dir, package_dir = build_inputs(
        tmp_path, rows=rows
    )
    build_slp_project(manifest_csv, images_dir, predictions_dir, package_dir, METADATA)
    shutil.copy2(manifest_csv, package_dir / "sample_manifest.csv")
    write_package_metadata(record or package_record(), package_dir)
    return package_dir


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

    message = str(excinfo.value)
    assert str(FRAME_COUNT - 1) in message and str(FRAME_COUNT) in message


def test_an_extra_curated_image_is_also_a_mismatch(tmp_path):
    """One-to-one runs both ways: an image no manifest row claims is unexplained data."""
    package_dir = complete_package(tmp_path)
    write_jpeg(package_dir / "images" / "not_in_the_manifest.jpg")

    with pytest.raises(ValueError) as excinfo:
        validate_package(package_dir)

    assert str(FRAME_COUNT + 1) in str(excinfo.value)


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
