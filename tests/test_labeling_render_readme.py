"""Characterization + deviation tests for the README renderer.

Sequenced per design.md Decision 1. The ``characterization`` tests pin what the port
inherited unchanged from the vault's ``generate_readme.py`` — the labeler-facing content,
which is good documentation and is not crop-specific. The ``deviation`` tests pin what
tasks 8.3a–8.3c change on purpose, each naming the legacy behavior it replaced.

The theme of the deviation is *where the content comes from*, not what it says. The vault
script stated the crop, the experiment, the Bloom id, the accession names, the project
filenames and the skeleton node counts as hardcoded text edited by hand per package
(design.md F7) — a second, hand-synced copy of things ``build_slp_project.py`` and the
package metadata already knew. All of it now renders from the ``PackageRecord``, so the
README is a view of the package's metadata rather than a restatement of it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import sleap_io as sio

from conftest import (
    SCANS,
    complete_package,
    manifest_rows,
    package_record,
    write_jpeg,
)
from sleap_roots_training.labeling.metadata import (
    PackageMetadata,
    write_package_metadata,
)
from sleap_roots_training.labeling.render_readme import render_readme


def render(tmp_path: Path, **kwargs) -> str:
    """Assemble a package, render its README, and return the text."""
    package_dir = complete_package(tmp_path, **kwargs)
    return render_readme(package_dir).read_text()


# --------------------------------------------------------------------------------------
# Characterization — the labeler-facing content, inherited unchanged
# --------------------------------------------------------------------------------------


def test_it_links_the_sleap_install_tutorial_and_notion_guide(tmp_path):
    readme = render(tmp_path)

    assert "https://sleap.ai/installation" in readme
    assert "https://sleap.ai/tutorials/tutorial.html" in readme
    assert "https://www.notion.so/1224a67a766780da8b64c8cab59939b2" in readme


def test_it_documents_the_versioning_convention(tmp_path):
    """``v000`` is predictions and is never overwritten — the rule the package depends on."""
    readme = render(tmp_path)

    assert "`v000` = model predictions" in readme
    assert "Always Save As a new version" in readme


def test_it_reports_the_plants_and_ages(tmp_path):
    readme = render(tmp_path)

    assert "2 plants sampled across ages: 3 DAG" in readme


def test_it_still_reads_as_the_same_document(tmp_path):
    """The rewrite changed the source of the content, not the document a labeler opens."""
    readme = render(tmp_path)

    for heading in (
        "## What Is This?",
        "## Getting Started",
        "## Package Contents",
        "## How to Open in SLEAP",
        "## About the Predictions",
        "## Versioning Convention",
        "## Skeleton Reference",
        "## Data Source",
    ):
        assert heading in readme


# --------------------------------------------------------------------------------------
# Deviation — the content comes from the record (task 8.3a, F7)
# --------------------------------------------------------------------------------------


def test_the_crop_and_experiment_come_from_the_record(tmp_path):
    """Replaces the hardcoded "Soybean WEEP", which was hand-edited per package.

    The command doc advertises five crops (Decision 7), so a renderer that can only
    describe one is a renderer that has to be edited before every other package.
    """
    readme = render(tmp_path)

    assert readme.startswith("# Soybean WEEP Labeling Package")
    assert "curated soybean images from the WEEP experiment" in readme


def test_a_different_crop_renders_without_editing_the_renderer(tmp_path):
    """The point of the deviation, stated as the case the vault script could not do."""
    rice = PackageMetadata(
        species="rice", mode="cylinder", experiment="dry2024", root_types=("primary",)
    )
    package_dir = complete_package(tmp_path)
    # Re-describe the same package as a rice one; only the record changes.
    shutil.move(
        str(package_dir / "soybean_weep_primary_labels.v000.slp"),
        str(package_dir / "rice_dry2024_primary_labels.v000.slp"),
    )
    (package_dir / "soybean_weep_lateral_labels.v000.slp").unlink()
    write_package_metadata(
        package_record(
            metadata=rice,
            skeletons={"primary": ("r1", "r2", "r3", "r4", "r5", "r6")},
        ),
        package_dir,
    )

    readme = render_readme(package_dir).read_text()

    assert readme.startswith("# Rice DRY2024 Labeling Package")
    assert "`rice_dry2024_primary_labels.v000.slp`" in readme
    assert "soybean" not in readme.lower()


def test_the_bloom_experiment_id_comes_from_the_record(tmp_path):
    """Replaces the hardcoded sentence. It is #10's trace back to source data."""
    readme = render(tmp_path, record=package_record(bloom_experiment_id=42424242))

    assert "Bloom experiment ID: 42424242" in readme


def test_the_accession_names_come_from_the_record(tmp_path):
    readme = render(tmp_path)

    assert "Accessions: A3244, WEEP-1-4" in readme


def test_an_accession_the_record_does_not_map_is_an_error_not_a_bare_number(tmp_path):
    """Replaces ``accession_map.get(a, a)``.

    The names are a human lookup against Bloom (design.md F2), so falling back to the
    numeric id documented a package's genotypes as numbers and reported success. An
    unmapped id means the lookup was not done.
    """
    rows = list(manifest_rows())
    for row in rows:
        row["accession_id"] = 99999999

    package_dir = complete_package(tmp_path, rows=rows)

    with pytest.raises(ValueError, match="99999999"):
        render_readme(package_dir)


def test_the_selection_parameters_are_published_to_the_reader(tmp_path):
    """New content, from 8.3's record: Decision 6's re-derive path needs the seed.

    Nothing in the vault package recorded them anywhere, in prose or otherwise.
    """
    readme = render(tmp_path)

    assert "- Seed: 42" in readme
    assert "- Plants per age x accession group: 5" in readme
    assert "- Rotational views per scan: 72" in readme


# --------------------------------------------------------------------------------------
# Deviation — the counts agree with the manifest or fail (task 8.3b, F7)
# --------------------------------------------------------------------------------------


def test_the_image_count_is_the_manifest_row_count(tmp_path):
    readme = render(tmp_path)

    assert "Total images: 6" in readme


def test_a_dropped_image_is_an_error_rather_than_a_smaller_number(tmp_path):
    """Replaces ``len(list(images_dir.glob("*.jpg")))``.

    The manifest is the record of what should be there; the glob was a record of what
    happened to be there. Publishing the second as the first turned a corrupted package
    into a package with a smaller number in its documentation — the only place the
    discrepancy appeared at all.
    """
    package_dir = complete_package(tmp_path)
    dropped = sorted((package_dir / "images").glob("*.jpg"))[0]
    dropped.unlink()

    with pytest.raises(ValueError) as excinfo:
        render_readme(package_dir)

    assert dropped.name in str(excinfo.value)


def test_a_declared_frame_count_that_disagrees_is_an_error(tmp_path):
    """The README is where a number reaches a human, so it runs the same rule."""
    package_dir = complete_package(tmp_path, record=package_record(frame_count=99))

    with pytest.raises(ValueError, match="99"):
        render_readme(package_dir)


def test_unequal_views_per_scan_are_reported_as_a_range(tmp_path):
    """Replaces ``len(rows) // plant_count``, which reported a number no plant had."""
    rows = [
        row
        for row in manifest_rows()
        if not (row["scan_id"] == 2 and row["view_index"] == 49)
    ]
    # frame_index must stay a contiguous rank within its scan for the builder.
    for index, row in enumerate(r for r in rows if r["scan_id"] == 2):
        row["frame_index"] = index

    readme = render(tmp_path, rows=rows, record=package_record(frame_count=5))

    assert "- 2-3 labeled views per scan" in readme


def test_views_are_counted_per_scan_not_per_plant(tmp_path):
    """RED against the port: a plant scanned at two ages inflated the reported range.

    Views are a property of a scan. Grouping by ``plant_qr_code`` made a plain 3-view
    package covering two ages claim "3-6 rotational views per plant" — a number no scan
    has and no parameter asked for.
    """
    rows = [dict(row) for row in manifest_rows()]
    # The same plant, scanned again at a later age: a second scan_id, same barcode. This
    # is the normal shape of a longitudinal experiment, and the reason `output_filename`
    # embeds the age at all.
    for row in list(rows):
        if row["scan_id"] == 1:
            later = dict(row)
            later["scan_id"] = 99
            later["plant_age_days"] = 5
            later["output_filename"] = later["output_filename"].replace("age3", "age5")
            rows.append(later)
    scans = SCANS + ((99, "9DK8KJJEZR", 5, 12742739, "A3244"),)

    readme = render(
        tmp_path,
        rows=rows,
        scans=scans,
        record=package_record(frame_count=len(rows)),
    )

    # Three views per scan, not the six the plant carries across its two scans.
    assert "- 3 labeled views per scan" in readme
    assert "6" not in readme.split("labeled views per scan")[0].splitlines()[-1]


# --------------------------------------------------------------------------------------
# Deviation — the skeleton description cannot drift from the .slp (task 8.3c, F7)
# --------------------------------------------------------------------------------------


def test_the_skeleton_reference_comes_from_the_record(tmp_path):
    readme = render(tmp_path)

    assert (
        "**Primary root** (6 nodes): `r1` (base) -> `r2` -> `r3` -> `r4` -> `r5` -> "
        "`r6` (tip)" in readme
    )
    assert (
        "**Lateral root** (4 nodes): `r1` (base) -> `r2` -> `r3` -> `r4` (tip)"
        in readme
    )


def test_the_documented_node_counts_match_the_skeleton_in_the_slp(tmp_path):
    """Task 8.3c, closed at the seam rather than by comparing two texts.

    The node counts were prose in ``generate_readme.py:58-60`` duplicating constants in
    ``build_slp_project.py:43-58``. The README now renders from the record, and
    ``validate_package`` requires the record to match the skeleton actually written — so
    the two can only agree. This asserts the end-to-end property directly.
    """
    package_dir = complete_package(tmp_path)
    readme = render_readme(package_dir).read_text()

    for root_type in ("primary", "lateral"):
        labels = sio.load_slp(
            str(package_dir / f"soybean_weep_{root_type}_labels.v000.slp"),
            open_videos=False,
        )
        nodes = list(labels.skeletons[0].node_names)
        assert f"**{root_type.capitalize()} root** ({len(nodes)} nodes)" in readme
        assert " -> ".join(f"`{n}`" for n in nodes[1:-1]) in readme


def test_the_package_contents_table_names_every_project_file(tmp_path):
    package_dir = complete_package(tmp_path)
    readme = render_readme(package_dir).read_text()

    for root_type in ("primary", "lateral"):
        assert f"| `soybean_weep_{root_type}_labels.v000.slp` |" in readme
    assert "| `sample_manifest.csv` |" in readme
    assert "| `package_metadata.yaml` |" in readme


def test_it_no_longer_tells_the_labeler_the_images_load_from_a_folder(tmp_path):
    """The embed change (section 5) made that instruction false."""
    readme = render(tmp_path)

    assert "embedded in the project file" in readme
    assert "load automatically from the `images/` folder" not in readme


def test_an_extra_curated_image_is_an_error(tmp_path):
    package_dir = complete_package(tmp_path)
    write_jpeg(package_dir / "images" / "unclaimed.jpg")

    with pytest.raises(ValueError, match="unclaimed.jpg"):
        render_readme(package_dir)
