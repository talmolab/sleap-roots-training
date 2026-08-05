"""Characterization + deviation tests for the image-copy step.

Sequenced per design.md Decision 1. The ``characterization`` tests pin what the port
inherited unchanged from the vault's ``copy_selected_images.py``; the ``deviation`` tests
pin what tasks 3.4, 3.5, and 3.5a change on purpose. Each deviation test names the legacy
behavior it replaced, so the two failures design.md records — the warn-and-continue that
reports success on an empty copy (F5) and the base-directory mismatch that triggers it
against correct data (F8) — stay readable after the fix lands.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.copy_images import copy_selected_images

#: One scan's `scan_path` in `bloomctl` form — relative to the directory holding
#: `scans.csv`, with no `images_downloader_output/` segment (design.md F8, verified from
#: `bloomctl`'s `cyl/download.py:47-51` and its own test).
BLOOMCTL_SCAN_PATH = "images/Wave1/Day3_20250101/9DK8KJJEZR"

#: The same scan in the legacy CLI's form, as `copy_selected_images.py:31` documents it:
#: one segment longer, relative to the *experiment* dir, with a `./` prefix. Inferred
#: from that comment — the legacy Node CLI has been removed and cannot be read — which is
#: also why its `scans.csv` is placed at the experiment root here.
LEGACY_SCAN_PATH = "./images_downloader_output/images/Wave1/Day3_20250101/9DK8KJJEZR"

#: Views the fixture manifest selects, out of a full 72-view rotation.
VIEWS = (1, 25, 49)

SCAN_ID = 1


def write_manifest(
    path: Path, scan_path: str, views=VIEWS, scan_id: int = SCAN_ID
) -> Path:
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


def write_scans_csv(path: Path, scan_path: str, scan_id: int = SCAN_ID) -> Path:
    """Write the ``scans.csv`` a manifest's paths are relative to."""
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["scan_id", "plant_qr_code", "scan_path"])
        writer.writerow([scan_id, "9DK8KJJEZR", scan_path])
    return path


def build_download(tmp_path: Path, view_names=range(1, 73)) -> tuple[Path, Path]:
    """Materialize a Bloom download tree, with each producer's ``scans.csv`` in place.

    The images sit at the one location both conventions ultimately name; only the
    ``scan_path`` written and the ``scans.csv`` it sits beside differ. Returns the
    ``bloomctl`` and legacy ``scans.csv`` paths, since the step is handed one of those
    rather than a directory.
    """
    experiment_dir = tmp_path / "WEEP_soybean"
    download_dir = experiment_dir / "images_downloader_output"
    scan_dir = download_dir / "images/Wave1/Day3_20250101/9DK8KJJEZR"
    scan_dir.mkdir(parents=True)
    for view_name in view_names:
        (scan_dir / f"{view_name}.jpg").write_bytes(f"jpeg-{view_name}".encode())
    return (
        write_scans_csv(download_dir / "scans.csv", BLOOMCTL_SCAN_PATH),
        write_scans_csv(experiment_dir / "scans.csv", LEGACY_SCAN_PATH),
    )


# --------------------------------------------------------------------------------------
# Characterization — behavior the port inherited unchanged
# --------------------------------------------------------------------------------------


def test_copies_each_row_under_its_curated_name(tmp_path):
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"

    assert copy_selected_images(manifest, bloomctl_scans, images_dir) == 3
    assert sorted(p.name for p in images_dir.iterdir()) == [
        "A3244_9DK8KJJEZR_age3_0.jpg",
        "A3244_9DK8KJJEZR_age3_1.jpg",
        "A3244_9DK8KJJEZR_age3_2.jpg",
    ]
    # The curated name is a rename, not a copy of the source name: view 25 becomes
    # frame 1. The builder reads `images/` by curated name, so this mapping is the only
    # thing keeping a frame pointed at its own image.
    assert (images_dir / "A3244_9DK8KJJEZR_age3_1.jpg").read_bytes() == b"jpeg-25"


def test_creates_the_destination_directory(tmp_path):
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/nested/images"
    assert not images_dir.exists()

    copy_selected_images(manifest, bloomctl_scans, images_dir)

    assert images_dir.is_dir()


def test_a_repeated_run_overwrites_rather_than_duplicating(tmp_path):
    """`shutil.copy2` still overwrites, which keeps re-running the step idempotent.

    Only the *silent* part of the vault behavior was a defect, and 3.5 removes it at its
    source — two rows can no longer claim one name. Overwriting an earlier run's output
    is the useful half and is preserved.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"
    images_dir.mkdir(parents=True)
    (images_dir / "A3244_9DK8KJJEZR_age3_0.jpg").write_bytes(b"stale")

    assert copy_selected_images(manifest, bloomctl_scans, images_dir) == 3
    assert (images_dir / "A3244_9DK8KJJEZR_age3_0.jpg").read_bytes() == b"jpeg-1"
    assert len(list(images_dir.iterdir())) == 3


# --------------------------------------------------------------------------------------
# Deviation (task 3.4) — explicit resolution, and no silent partial copy
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("producer", ["bloomctl", "legacy"])
def test_each_producers_manifest_resolves_against_its_own_scans_csv(tmp_path, producer):
    """F8 closed, without detecting which producer wrote the manifest.

    The vault script joined `source_image` to `experiment_dir`, which resolved the
    legacy convention and missed *every* row of a `bloomctl` export by exactly one path
    segment — an empty `images/` and a zero exit, with correct and present data.
    Resolving against the directory holding the manifest's own `scans.csv` is true of
    both producers by construction, so neither needs to be recognized.
    """
    bloomctl_scans, legacy_scans = build_download(tmp_path)
    scans_csv, scan_path = (
        (bloomctl_scans, BLOOMCTL_SCAN_PATH)
        if producer == "bloomctl"
        else (legacy_scans, LEGACY_SCAN_PATH)
    )
    manifest = write_manifest(tmp_path / "sample_manifest.csv", scan_path)
    images_dir = tmp_path / "package/images"

    assert copy_selected_images(manifest, scans_csv, images_dir) == 3
    assert len(list(images_dir.iterdir())) == 3


def test_a_missing_source_image_fails_the_step_and_writes_nothing(tmp_path):
    """Replaces the F5 warn-and-continue: a partial copy is no longer a completed step.

    The scan holds a full 72 images but under an off-by-one naming (`0.jpg`..`71.jpg`),
    so the view-count check passes and the row for view 72 is the one that cannot
    resolve — the case where the per-row check is the only thing standing between a
    hand-edited or oddly-named scan and a package missing a frame.
    """
    bloomctl_scans, _ = build_download(tmp_path, view_names=range(0, 72))
    manifest = write_manifest(
        tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH, views=(1, 25, 72)
    )
    images_dir = tmp_path / "package/images"

    with pytest.raises(FileNotFoundError) as excinfo:
        copy_selected_images(manifest, bloomctl_scans, images_dir)

    assert "1 of 3" in str(excinfo.value)
    assert "72.jpg" in str(excinfo.value)
    assert "A3244_9DK8KJJEZR_age3_2.jpg" in str(excinfo.value)
    # Nothing is written, so no later stage can mistake a failed copy for a done one.
    assert not images_dir.exists()


def test_the_wrong_scans_csv_is_named_rather_than_yielding_an_empty_copy(tmp_path):
    """The F8 failure re-opened one layer up, and closed there too.

    Deriving the base from `scans.csv` would still let a caller point at the wrong one.
    Checking that every manifest row's `(scan_id, source_scan_path)` is described by
    that file turns a silent empty copy into an error naming the scan — which is what
    task 7.2 relies on in choosing this over carrying the base as a manifest column.
    """
    _, legacy_scans = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)

    with pytest.raises(ValueError) as excinfo:
        copy_selected_images(manifest, legacy_scans, tmp_path / "package/images")

    assert "not described by" in str(excinfo.value)
    assert BLOOMCTL_SCAN_PATH in str(excinfo.value)
    assert "scan_id 1" in str(excinfo.value)


def test_a_file_that_is_not_a_scans_csv_is_rejected_by_name(tmp_path):
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    not_scans = tmp_path / "not_scans.csv"
    not_scans.write_text("scan_id,something_else\n1,x\n")

    with pytest.raises(ValueError, match="scan_path"):
        copy_selected_images(manifest, not_scans, tmp_path / "package/images")


def test_an_absolute_source_path_is_rejected_rather_than_mangled(tmp_path):
    """Replaces the `lstrip("./")` character-strip.

    Task 0.9 established Bloom never emits an absolute path, so there is no shipped
    behavior to preserve — but the strip ate a leading separator rather than failing,
    which would have reported every row missing with nothing actually absent.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(
        tmp_path / "sample_manifest.csv", "/mnt/hpi_dev/images/Wave1/Day3/QR"
    )

    with pytest.raises(ValueError, match="absolute"):
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")


def test_a_missing_scan_directory_names_the_path(tmp_path):
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(
        tmp_path / "sample_manifest.csv", "images/Wave1/Day3_20250101/NOSUCHQR"
    )
    # Describe the absent scan in scans.csv, so this is the directory check firing and
    # not the manifest/scans cross-check.
    write_scans_csv(bloomctl_scans, "images/Wave1/Day3_20250101/NOSUCHQR")

    with pytest.raises(FileNotFoundError, match="NOSUCHQR"):
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")


def test_a_missing_required_column_is_named(tmp_path):
    bloomctl_scans, _ = build_download(tmp_path)
    manifest_path = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    rows = list(csv.DictReader(manifest_path.open()))
    columns = [c for c in ss.MANIFEST_COLUMNS if c != "source_scan_path"]
    with manifest_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="source_scan_path"):
        copy_selected_images(manifest_path, bloomctl_scans, tmp_path / "package/images")


# --------------------------------------------------------------------------------------
# Deviation (task 3.5) — a duplicate curated name is the second line of defence
# --------------------------------------------------------------------------------------


def test_a_duplicate_output_filename_is_rejected_before_anything_is_copied(tmp_path):
    """Pairs with task 2.9, which catches this at selection time.

    A hand-edited manifest reaches this step directly, and the vault behavior absorbed
    it completely: `shutil.copy2` overwrote, and `copied` counted calls rather than
    resulting files, so N rows collapsed into fewer images while every count still read
    correct. Both callers now enforce the one rule that lives with the manifest writer.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest_path = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    rows = list(csv.DictReader(manifest_path.open()))
    rows[1]["output_filename"] = rows[0]["output_filename"]
    with manifest_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    images_dir = tmp_path / "package/images"

    with pytest.raises(ValueError) as excinfo:
        copy_selected_images(manifest_path, bloomctl_scans, images_dir)

    assert "A3244_9DK8KJJEZR_age3_0.jpg" in str(excinfo.value)
    assert not images_dir.exists()


# --------------------------------------------------------------------------------------
# Deviation (task 3.5a) — the obligation task 2.5 left here
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("present", [36, 96])
def test_a_scan_whose_view_count_contradicts_the_assumption_names_it(tmp_path, present):
    """One wrong parameter reports as one wrong parameter, not as N missing files.

    Selection reads only CSVs (design.md F2), so it cannot check `total_views` against
    what a scan actually holds; this is the first stage that sees the images. Both
    directions fail: too few and the manifest names files that do not exist, too many
    and the selected indices are the wrong angles.
    """
    bloomctl_scans, _ = build_download(tmp_path, view_names=range(1, present + 1))
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"

    with pytest.raises(ValueError) as excinfo:
        copy_selected_images(manifest, bloomctl_scans, images_dir)

    message = str(excinfo.value)
    assert f"holds {present} rotational view" in message
    assert "total_views=72" in message
    assert f"total_views={present}" in message
    assert not images_dir.exists()


def test_the_view_count_check_uses_the_selection_parameter_it_was_given(tmp_path):
    """A non-72 experiment is buildable — the check pins agreement, not the number 72."""
    bloomctl_scans, _ = build_download(tmp_path, view_names=range(1, 37))
    manifest = write_manifest(
        tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH, views=(1, 13, 25)
    )

    copied = copy_selected_images(
        manifest, bloomctl_scans, tmp_path / "package/images", total_views=36
    )

    assert copied == 3


def test_the_default_view_count_is_the_one_selection_defaults_to(tmp_path):
    """The two stages must not drift: a default of 72 here and 72 there is the contract."""
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)

    assert ss.TOTAL_VIEWS == 72
    assert (
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images") == 3
    )


def test_non_view_files_in_the_scan_directory_do_not_count_as_views(tmp_path):
    """QC and download leave sidecars; only `<int>.jpg` is a rotational view."""
    bloomctl_scans, _ = build_download(tmp_path)
    scan_dir = bloomctl_scans.parent / "images/Wave1/Day3_20250101/9DK8KJJEZR"
    (scan_dir / "thumbnail.jpg").write_bytes(b"not-a-view")
    (scan_dir / "metadata.json").write_text("{}")
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)

    assert (
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images") == 3
    )
