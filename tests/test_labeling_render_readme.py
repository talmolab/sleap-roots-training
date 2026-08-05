"""Characterization tests for the README renderer, before task 8.3a changes it.

design.md Decision 1: the port is on the record before anything about it changes. These
tests pin what ``generate_readme.py`` shipped — including the three defects design.md F7
records, which are pinned here as *current behavior* and reversed by the deviation commit:

* the crop, the experiment, the Bloom id, the accession names, the project filenames and
  the skeleton node counts are all hardcoded, so the file was hand-edited per package and
  its skeleton prose duplicates ``build_slp_project.py``'s constants with nothing keeping
  them in step;
* the image count is globbed from ``images/`` rather than read from the manifest, so a
  dropped image is silently reported as a smaller number instead of as an error;
* views per plant is ``len(rows) // plant_count``, which misreports whenever plants
  contribute unequal numbers of views.
"""

from __future__ import annotations

from pathlib import Path

from conftest import write_jpeg
from test_labeling_build_package import manifest_rows, write_manifest
from sleap_roots_training.labeling.render_readme import generate_readme


def staged(tmp_path: Path, rows=None, images=None):
    """Stage a manifest and a curated images directory; return both plus the rows."""
    rows = list(rows if rows is not None else manifest_rows())
    manifest_csv = tmp_path / "sample_manifest.csv"
    write_manifest(manifest_csv, rows)
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for row in images if images is not None else rows:
        write_jpeg(images_dir / row["output_filename"])
    return manifest_csv, images_dir, rows


def render(tmp_path: Path, **kwargs) -> str:
    """Render the README over the standard fixture and return its text."""
    manifest_csv, images_dir, _ = staged(tmp_path, **kwargs)
    output = tmp_path / "README.md"
    generate_readme(manifest_csv, images_dir, output)
    return output.read_text()


# --------------------------------------------------------------------------------------
# Characterization — the labeler-facing content, which the deviation keeps
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


def test_it_reports_the_plants_ages_and_accession_names(tmp_path):
    readme = render(tmp_path)

    assert "2 plants sampled across ages: 3 DAG" in readme
    assert "A3244, WEEP-1-4" in readme


# --------------------------------------------------------------------------------------
# Characterization — the hardcoding (F7), which the deviation replaces
# --------------------------------------------------------------------------------------


def test_the_crop_and_experiment_are_hardcoded_soybean_weep(tmp_path):
    """Hand-edited per package. The command doc advertises five crops (Decision 7)."""
    readme = render(tmp_path)

    assert readme.startswith("# Soybean WEEP Labeling Package")
    assert "curated soybean images from the WEEP experiment" in readme


def test_the_bloom_experiment_id_is_hardcoded_prose(tmp_path):
    """The trace back to source data that #10's ``LabelCard`` needs, unparseable."""
    readme = render(tmp_path)

    assert "Bloom experiment: WEEP_Soybean (ID 10102496)" in readme


def test_the_project_filenames_are_hardcoded(tmp_path):
    readme = render(tmp_path)

    assert "`soybean_weep_primary_labels.v000.slp`" in readme
    assert "`soybean_weep_lateral_labels.v000.slp`" in readme


def test_the_skeleton_node_counts_are_prose_duplicating_the_builders_constants(
    tmp_path,
):
    """F7. Nothing compares this text to the skeleton actually written into the .slp."""
    readme = render(tmp_path)

    assert "Primary root predictions (6 nodes: r1-r6)" in readme
    assert "**Primary root** (6 nodes): `r1` (base/seed) -> `r2`" in readme
    assert "**Lateral root** (4 nodes): `r1` (base/attachment) -> `r2`" in readme


def test_an_unmapped_accession_id_renders_as_the_raw_id(tmp_path):
    """The map is three hardcoded WEEP entries; every other experiment gets numbers."""
    rows = list(manifest_rows())
    for row in rows:
        row["accession_id"] = 99999999
        row["accession_name"] = "UNKNOWN"

    readme = render(tmp_path, rows=rows)

    assert "Accessions: 99999999" in readme


# --------------------------------------------------------------------------------------
# Characterization — the counts (F7), which the deviation makes agree or fail
# --------------------------------------------------------------------------------------


def test_the_image_count_is_globbed_so_a_dropped_image_is_reported_not_raised(tmp_path):
    """The defect 8.3b reverses.

    The manifest is the record of what should be there; the glob is a record of what
    happens to be there. Reporting the second as though it were the first turns a
    corrupted package into a package with a smaller number in its documentation.
    """
    rows = list(manifest_rows())

    readme = render(tmp_path, rows=rows, images=rows[:-1])

    assert "Total images: 5" in readme
    assert len(rows) == 6


def test_views_per_plant_is_integer_division_over_the_row_count(tmp_path):
    """Right only when every plant contributes the same number of views.

    Unequal views are not hypothetical: a scan short of its full rotation, or a widened
    re-selection, produces them, and this reports a number no plant actually has.
    """
    rows = [
        row
        for row in manifest_rows()
        if not (row["scan_id"] == 2 and row["view_index"] == 49)
    ]

    readme = render(tmp_path, rows=rows)

    # 5 rows across 2 plants -> "2 rotational views per plant", true of neither plant.
    assert "- 2 rotational views per plant" in readme
