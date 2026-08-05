"""Task 8.5 — the labeling package generator as a public, scriptable command.

The spec's Labeling Package CLI requirement exists because this workflow lived in a
personal vault repo driven by four `uv run` invocations against hardcoded Windows paths
(design.md, Context). "Reachable from the repo's click CLI, mirroring how the registry
commands are exposed" is what makes it something another person can run.

Mirrors ``tests/test_registry_cli.py``: every failure has to arrive as a clean
``Error: ...``, not as a traceback with the message buried in it.
"""

from __future__ import annotations

import json
import shutil

import pytest
from click.testing import CliRunner

from test_labeling_package import ACCESSIONS, TOTAL_VIEWS, download
from sleap_roots_training import cli
from sleap_roots_training.labeling.metadata import PACKAGE_METADATA_FILENAME
from sleap_roots_training.labeling.validate import validate_package


def invoke(args):
    return CliRunner().invoke(cli.main, ["labeling", *args])


def build_args(tmp_path, **overrides):
    """The full argument list for a successful ``labeling build``."""
    manifest_csv, scans_csv, predictions_dir = download(tmp_path)
    args = {
        "--manifest": str(manifest_csv),
        "--scans-csv": str(scans_csv),
        "--predictions-dir": str(predictions_dir),
        "--output-dir": str(tmp_path / "soybean-weep-labeling"),
        "--species": "soybean",
        "--mode": "cylinder",
        "--experiment": "weep",
        "--bloom-experiment-id": "10102496",
        "--accessions": json.dumps(ACCESSIONS),
        "--seed": "42",
        "--plants-per-group": "5",
        "--views-per-plant": "3",
        "--total-views": str(TOTAL_VIEWS),
    }
    args.update(overrides)
    flat = [item for pair in args.items() for item in pair]
    return flat + ["--root-type", "primary", "--root-type", "lateral"]


# --------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------


def test_build_writes_a_validated_package_and_reports_its_path(tmp_path):
    result = invoke(["build", *build_args(tmp_path)])

    assert result.exit_code == 0, result.output
    package_dir = tmp_path / "soybean-weep-labeling"
    assert str(package_dir) in result.output
    validate_package(package_dir)


def test_build_reports_what_it_wrote(tmp_path):
    result = invoke(["build", *build_args(tmp_path)])

    assert "6 frames" in result.output
    assert "soybean_weep_primary_labels.v000.slp" in result.output
    assert "soybean_weep_lateral_labels.v000.slp" in result.output


def test_build_failure_is_a_clean_error_and_writes_nothing(tmp_path):
    """The spec's "exits non-zero with the validation error, and does not write a package".

    A scan with no predictions is the section-4 failure; what this pins is that it reaches
    an operator as an error rather than as a traceback, and leaves no directory behind.
    """
    args = build_args(tmp_path)
    for path in (tmp_path / "sleap_roots_traits_input").glob("scan_2.*"):
        path.unlink()

    result = invoke(["build", *args])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "no predictions" in result.output
    assert not (tmp_path / "soybean-weep-labeling").exists()
    assert not isinstance(result.exception, ValueError)


def test_build_rejects_an_out_of_vocabulary_species_by_name(tmp_path):
    result = invoke(["build", *build_args(tmp_path, **{"--species": "wheat"})])

    assert result.exit_code != 0
    assert "species" in result.output
    assert not isinstance(result.exception, ValueError)


def test_build_rejects_a_crop_the_skeleton_table_does_not_cover(tmp_path):
    """Decision 7: pennycress has no row on purpose, so it fails rather than guessing."""
    result = invoke(
        [
            "build",
            *build_args(
                tmp_path, **{"--species": "pennycress", "--experiment": "trial"}
            ),
        ]
    )

    assert result.exit_code != 0
    assert "pennycress" in result.output
    assert not isinstance(result.exception, ValueError)


def test_build_refuses_an_existing_output_directory(tmp_path):
    args = build_args(tmp_path)
    (tmp_path / "soybean-weep-labeling").mkdir()

    result = invoke(["build", *args])

    assert result.exit_code != 0
    assert "exists" in result.output


def test_build_rejects_malformed_accessions_json(tmp_path):
    result = invoke(["build", *build_args(tmp_path, **{"--accessions": "{not json"})])

    assert result.exit_code != 0
    assert "accessions" in result.output.lower()
    assert not isinstance(result.exception, ValueError)


def test_build_rejects_accessions_that_are_not_a_mapping(tmp_path):
    result = invoke(
        [
            "build",
            *build_args(tmp_path, **{"--accessions": json.dumps(["A3244"])}),
        ]
    )

    assert result.exit_code != 0
    assert "accessions" in result.output.lower()


def test_build_reads_accessions_from_a_file(tmp_path):
    """The map comes from a hand-run Bloom query (F2); pasting JSON into a shell is how
    a quote gets lost. ``@path`` keeps the lookup's output as a file."""
    accessions = tmp_path / "accessions.json"
    accessions.write_text(json.dumps(ACCESSIONS))

    result = invoke(
        ["build", *build_args(tmp_path, **{"--accessions": f"@{accessions}"})]
    )

    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------------------


def test_validate_accepts_a_built_package(tmp_path):
    invoke(["build", *build_args(tmp_path)])

    result = invoke(["validate", str(tmp_path / "soybean-weep-labeling")])

    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_reports_what_the_package_holds(tmp_path):
    invoke(["build", *build_args(tmp_path)])

    result = invoke(["validate", str(tmp_path / "soybean-weep-labeling")])

    assert "6" in result.output
    assert "soybean" in result.output


def test_validate_rejects_an_incomplete_package_as_a_clean_error(tmp_path):
    invoke(["build", *build_args(tmp_path)])
    package_dir = tmp_path / "soybean-weep-labeling"
    (package_dir / "sample_manifest.csv").unlink()

    result = invoke(["validate", str(package_dir)])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "sample_manifest.csv" in result.output
    assert not isinstance(result.exception, ValueError)


def test_validate_rejects_a_directory_that_is_not_a_package(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    result = invoke(["validate", str(empty)])

    assert result.exit_code != 0
    assert PACKAGE_METADATA_FILENAME in result.output
    assert not isinstance(result.exception, FileNotFoundError)


def test_validate_is_what_publish_labels_will_call(tmp_path):
    """A delivered package validates where it lands, not only where it was built."""
    invoke(["build", *build_args(tmp_path)])
    delivered = tmp_path / "delivered/soybean-weep-labeling"
    delivered.parent.mkdir()
    shutil.move(str(tmp_path / "soybean-weep-labeling"), str(delivered))
    shutil.rmtree(tmp_path / "WEEP_soybean")

    result = invoke(["validate", str(delivered)])

    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------------------
# select and copy-images — the stages the workflow doc drives separately
# --------------------------------------------------------------------------------------


def test_select_writes_a_manifest(tmp_path):
    from test_labeling_select_samples import write_cleaned, write_scans

    scans_csv = write_scans(tmp_path)
    cleaned_csv = write_cleaned(tmp_path)
    output_csv = tmp_path / "sample_manifest.csv"

    result = invoke(
        [
            "select",
            "--cleaned-csv",
            str(cleaned_csv),
            "--scans-csv",
            str(scans_csv),
            "--output-csv",
            str(output_csv),
            "--plants-per-group",
            "1",
            "--views-per-plant",
            "3",
        ]
    )

    assert result.exit_code == 0, result.output
    assert output_csv.is_file()
    assert str(output_csv) in result.output


def test_copy_images_populates_the_curated_directory(tmp_path):
    manifest_csv, scans_csv, _ = download(tmp_path)
    images_dir = tmp_path / "package/images"

    result = invoke(
        [
            "copy-images",
            "--manifest",
            str(manifest_csv),
            "--scans-csv",
            str(scans_csv),
            "--output-dir",
            str(images_dir),
            "--total-views",
            str(TOTAL_VIEWS),
        ]
    )

    assert result.exit_code == 0, result.output
    assert len(list(images_dir.glob("*.jpg"))) == 6


def test_copy_images_failure_is_a_clean_error(tmp_path):
    manifest_csv, scans_csv, _ = download(tmp_path)
    shutil.rmtree(scans_csv.parent / "images/Wave1/Day3_20250101/9DK8KJJEZR")
    images_dir = tmp_path / "package/images"

    result = invoke(
        [
            "copy-images",
            "--manifest",
            str(manifest_csv),
            "--scans-csv",
            str(scans_csv),
            "--output-dir",
            str(images_dir),
            "--total-views",
            str(TOTAL_VIEWS),
        ]
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert not images_dir.exists()
    assert not isinstance(result.exception, (OSError, ValueError))


@pytest.mark.parametrize("command", ["select", "copy-images", "build", "validate"])
def test_every_labeling_command_is_discoverable(command):
    result = CliRunner().invoke(cli.main, ["labeling", "--help"])

    assert result.exit_code == 0
    assert command in result.output
