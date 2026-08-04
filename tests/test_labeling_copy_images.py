"""Characterization tests for the image-copy step, before it is made fail-loud.

Sequenced per design.md Decision 1: these pin the behavior the port inherited from the
vault's ``copy_selected_images.py``, including the two defects design.md records — the
warn-and-continue that reports success on an empty copy (F5), and the base-directory
mismatch that triggers it against correct, complete data (F8). Task 3.4 changes both, in
its own commit; until then this file is the record of what the eight published
collections were produced by.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.copy_images import copy_selected_images

#: One scan, three selected views. `scan_path` is in `bloomctl` form — relative to the
#: directory holding `scans.csv`, with no `images_downloader_output/` segment
#: (design.md F8, verified from `bloomctl`'s `cyl/download.py:47-51`).
BLOOMCTL_SCAN_PATH = "images/Wave1/Day3_20250101/9DK8KJJEZR"

#: The same scan in the legacy CLI's form, as `copy_selected_images.py:31` documents it:
#: one segment longer, relative to the *experiment* dir, with a `./` prefix. Inferred
#: from that comment — the legacy Node CLI has been removed and cannot be read.
LEGACY_SCAN_PATH = "./images_downloader_output/images/Wave1/Day3_20250101/9DK8KJJEZR"

VIEWS = (1, 25, 49)


def write_manifest(path: Path, scan_path: str, views=VIEWS, scan_id: int = 1) -> Path:
    """Write a full-column ``sample_manifest.csv`` for one scan's selected views."""
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        for frame_index, view_index in enumerate(views):
            writer.writerow(
                {
                    "scan_id": scan_id,
                    "plant_qr_code": "9DK8KJJEZR",
                    "plant_age_days": 3,
                    "accession_id": 12742739,
                    "accession_name": "A3244",
                    "wave_number": 1,
                    "view_index": view_index,
                    "frame_index": frame_index,
                    "source_scan_path": scan_path,
                    "source_image": f"{scan_path}/{view_index}.jpg",
                    "output_filename": f"A3244_9DK8KJJEZR_age3_{frame_index}.jpg",
                }
            )
    return path


def build_download(tmp_path: Path, views=VIEWS) -> tuple[Path, Path]:
    """Materialize a Bloom download tree and return ``(experiment_dir, download_dir)``.

    The images sit at the one location both conventions ultimately name; only the
    manifest's ``scan_path`` and the base it is resolved against differ between them.
    """
    experiment_dir = tmp_path / "WEEP_soybean"
    download_dir = experiment_dir / "images_downloader_output"
    scan_dir = download_dir / "images/Wave1/Day3_20250101/9DK8KJJEZR"
    scan_dir.mkdir(parents=True)
    for view_index in views:
        (scan_dir / f"{view_index}.jpg").write_bytes(b"jpeg-%d" % view_index)
    (download_dir / "scans.csv").write_text("scan_id,scan_path\n")
    return experiment_dir, download_dir


# --------------------------------------------------------------------------------------
# Characterization — behavior the port inherited unchanged
# --------------------------------------------------------------------------------------


def test_copies_each_row_under_its_curated_name(tmp_path):
    experiment_dir, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", LEGACY_SCAN_PATH)
    images_dir = tmp_path / "package/images"

    copied, missing = copy_selected_images(manifest, experiment_dir, images_dir)

    assert (copied, missing) == (3, 0)
    assert sorted(p.name for p in images_dir.iterdir()) == [
        "A3244_9DK8KJJEZR_age3_0.jpg",
        "A3244_9DK8KJJEZR_age3_1.jpg",
        "A3244_9DK8KJJEZR_age3_2.jpg",
    ]
    # The curated name is a rename, not a copy of the source name: view 25 becomes
    # frame 1. The builder reads `images/` by curated name, so this mapping is the
    # only thing that keeps a frame pointing at its own image.
    assert (images_dir / "A3244_9DK8KJJEZR_age3_1.jpg").read_bytes() == b"jpeg-25"


def test_creates_the_destination_directory(tmp_path):
    experiment_dir, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", LEGACY_SCAN_PATH)
    images_dir = tmp_path / "package/nested/images"
    assert not images_dir.exists()

    copy_selected_images(manifest, experiment_dir, images_dir)

    assert images_dir.is_dir()


def test_an_existing_destination_file_is_overwritten_silently(tmp_path):
    """`shutil.copy2` does not complain, which is what makes an F6 collision invisible."""
    experiment_dir, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", LEGACY_SCAN_PATH)
    images_dir = tmp_path / "package/images"
    images_dir.mkdir(parents=True)
    stale = images_dir / "A3244_9DK8KJJEZR_age3_0.jpg"
    stale.write_bytes(b"stale")

    copied, missing = copy_selected_images(manifest, experiment_dir, images_dir)

    assert (copied, missing) == (3, 0)
    assert stale.read_bytes() == b"jpeg-1"


def test_the_copied_count_counts_calls_not_resulting_files(tmp_path):
    """Two rows sharing an ``output_filename`` collapse into one file, still counted twice.

    This is design.md F6 reaching the filesystem: `copied` reports the manifest row
    count, so every downstream check that trusts it reads correct while the package
    holds fewer images than it claims. Task 2.9 catches the duplicate at selection
    time; 3.5 adds the second line of defence here, for a hand-edited manifest.
    """
    experiment_dir, _ = build_download(tmp_path)
    manifest_path = tmp_path / "sample_manifest.csv"
    write_manifest(manifest_path, LEGACY_SCAN_PATH)
    rows = list(csv.DictReader(manifest_path.open()))
    rows[1]["output_filename"] = rows[0]["output_filename"]
    with manifest_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    images_dir = tmp_path / "package/images"

    copied, missing = copy_selected_images(manifest_path, experiment_dir, images_dir)

    assert copied == 3
    assert missing == 0
    assert len(list(images_dir.iterdir())) == 2


def test_a_missing_source_warns_and_the_step_still_returns(tmp_path, caplog):
    """The F5 warn-and-continue: a partial copy is reported as a completed step."""
    experiment_dir, download_dir = build_download(tmp_path, views=(1, 25))
    manifest = write_manifest(tmp_path / "sample_manifest.csv", LEGACY_SCAN_PATH)
    images_dir = tmp_path / "package/images"

    with caplog.at_level("WARNING"):
        copied, missing = copy_selected_images(manifest, experiment_dir, images_dir)

    assert (copied, missing) == (2, 1)
    assert "49.jpg" in caplog.text
    assert len(list(images_dir.iterdir())) == 2
    assert download_dir.exists()


# --------------------------------------------------------------------------------------
# Characterization — the F8 base-directory mismatch
# --------------------------------------------------------------------------------------


def test_the_legacy_scan_path_convention_resolves(tmp_path):
    """The convention the vault script was written against, with its documented base."""
    experiment_dir, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", LEGACY_SCAN_PATH)

    copied, missing = copy_selected_images(
        manifest, experiment_dir, tmp_path / "package/images"
    )

    assert (copied, missing) == (3, 0)


def test_a_bloomctl_scan_path_misses_every_row_by_one_segment(tmp_path, caplog):
    """Correct, complete, present data — and the step reports success with nothing copied.

    This is design.md F8: `bloomctl` writes `scan_path` relative to the download dir,
    the step resolves it against the *experiment* dir, and the two differ by exactly
    `images_downloader_output/`. Every row warns, the directory is created empty, and
    nothing in the return value distinguishes this from a scan with no images.
    """
    experiment_dir, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"

    with caplog.at_level("WARNING"):
        copied, missing = copy_selected_images(manifest, experiment_dir, images_dir)

    assert (copied, missing) == (0, 3)
    assert list(images_dir.iterdir()) == []
    # The path it looked at is the experiment dir's, one segment short of the images.
    assert str(experiment_dir / "images/Wave1") in caplog.text


def test_a_bloomctl_scan_path_resolves_against_the_download_dir(tmp_path):
    """The same manifest resolves when handed the base its paths are actually relative to.

    Pins that F8 is a base-directory mismatch and nothing else — the data is fine, the
    manifest is fine, and only the argument is wrong. That is what makes it a design
    defect rather than a bad input: the caller is told to pass `experiment_dir`.
    """
    _, download_dir = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)

    copied, missing = copy_selected_images(
        manifest, download_dir, tmp_path / "package/images"
    )

    assert (copied, missing) == (3, 0)


@pytest.mark.parametrize(
    "scan_path, base",
    [(LEGACY_SCAN_PATH, "experiment"), (BLOOMCTL_SCAN_PATH, "download")],
)
def test_no_convention_resolves_against_both_bases(tmp_path, scan_path, base):
    """Neither form works against the other's base, so guessing is not an option.

    Task 3.4 must resolve this by being told the base explicitly rather than by
    detecting which producer wrote the manifest.
    """
    experiment_dir, download_dir = build_download(tmp_path)
    wrong_base = download_dir if base == "experiment" else experiment_dir
    manifest = write_manifest(tmp_path / "sample_manifest.csv", scan_path)

    copied, missing = copy_selected_images(
        manifest, wrong_base, tmp_path / "package/images"
    )

    assert (copied, missing) == (0, 3)
