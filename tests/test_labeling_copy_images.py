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
import shutil
from pathlib import Path
from unittest import mock

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


def test_a_repeated_run_replaces_the_previous_output(tmp_path):
    """Re-running the step stays idempotent, and now clears an earlier run's leftovers.

    Overwriting is the useful half of the vault behavior and is preserved. What changes
    (blocking review of #40) is that the destination is *replaced* rather than merged
    into: a file an earlier run wrote under different parameters used to survive, and then
    surfaced several stages later as a counts mismatch blaming the manifest.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"
    images_dir.mkdir(parents=True)
    (images_dir / "A3244_9DK8KJJEZR_age3_0.jpg").write_bytes(b"stale")
    (images_dir / "from_a_narrower_run.jpg").write_bytes(b"orphan")

    assert copy_selected_images(manifest, bloomctl_scans, images_dir) == 3
    assert (images_dir / "A3244_9DK8KJJEZR_age3_0.jpg").read_bytes() == b"jpeg-1"
    assert not (images_dir / "from_a_narrower_run.jpg").exists()
    assert len(list(images_dir.iterdir())) == 3


@pytest.mark.parametrize(
    "leftover", ["notes.txt", "sleap_roots_training", "important.slp"]
)
def test_a_destination_holding_anything_but_images_is_refused(tmp_path, leftover):
    """`--output-dir` is a free path, and the step now replaces its destination.

    A mistyped value would otherwise hand an arbitrary directory tree to `shutil.rmtree`.
    This module is careful about the same class on the read side (`_assert_contained_
    relative`, `assert_unique_output_filenames`); the write side had no equivalent.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "somewhere_else"
    images_dir.mkdir()
    if leftover == "sleap_roots_training":
        (images_dir / leftover).mkdir()
    else:
        (images_dir / leftover).write_text("not a curated frame")

    with pytest.raises(ValueError, match="not curated images"):
        copy_selected_images(manifest, bloomctl_scans, images_dir)

    assert (images_dir / leftover).exists()


def test_a_destination_that_is_a_file_is_refused(tmp_path):
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    not_a_dir = tmp_path / "images"
    not_a_dir.write_text("this is a file")

    with pytest.raises(ValueError, match="is not a directory"):
        copy_selected_images(manifest, bloomctl_scans, not_a_dir)

    assert not_a_dir.read_text() == "this is a file"


def test_a_failed_move_restores_the_previous_images_directory(tmp_path):
    """The rollback path, which is the whole reason the move is two renames.

    Deleting the destination and then renaming is two syscalls; a crash between them
    leaves the destination gone and the finished copy under a temporary name. Renaming the
    old directory aside first means the destination only ever holds the old contents or
    the new ones — including when the second rename fails.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"
    images_dir.mkdir(parents=True)
    (images_dir / "A3244_9DK8KJJEZR_age3_0.jpg").write_bytes(b"previous run")

    real_rename = Path.rename

    def fail_moving_staging_into_place(self, target):
        # Only the staging -> destination move; the rollback that puts the old directory
        # back is the behaviour under test and must be allowed through.
        if ".partial-" in Path(self).name and Path(target) == images_dir:
            raise OSError(39, "Directory not empty")
        return real_rename(self, target)

    with mock.patch.object(Path, "rename", fail_moving_staging_into_place):
        with pytest.raises(OSError, match="Directory not empty"):
            copy_selected_images(manifest, bloomctl_scans, images_dir)

    assert (images_dir / "A3244_9DK8KJJEZR_age3_0.jpg").read_bytes() == b"previous run"
    assert not list(tmp_path.glob("package/*.superseded-*"))


def test_a_failed_copy_leaves_no_partial_images_directory(tmp_path):
    """RED against the port: a mid-loop OSError left a partial `images/` behind.

    ENOSPC, a Box or NFS mount dropping, a permissions change — any of them stopped the
    loop with some files already written, contradicting this step's own all-or-nothing
    docstring and the CLI help. The failure is injected at the last copy so the earlier
    ones have genuinely happened.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    images_dir = tmp_path / "package/images"

    real_copy2, calls = shutil.copy2, []

    def failing_copy2(src, dst, **kwargs):
        calls.append(dst)
        if len(calls) == 3:
            raise OSError(28, "No space left on device")
        return real_copy2(src, dst, **kwargs)

    with mock.patch.object(shutil, "copy2", failing_copy2):
        with pytest.raises(OSError, match="No space left on device"):
            copy_selected_images(manifest, bloomctl_scans, images_dir)

    assert len(calls) == 3, "the failure must land mid-loop, not on the first copy"
    assert not images_dir.exists()
    # And no staging directory survives to be mistaken for one later.
    assert not list((tmp_path / "package").glob("*partial*"))


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


@pytest.mark.parametrize(
    "scan_path",
    [
        "/mnt/hpi_dev/images/Wave1/Day3/QR",
        # A Windows drive letter. `PurePosixPath("C:/...").is_absolute()` is False, so the
        # guard this replaces let it through and joined it onto the base anyway. design.md
        # F11 records that the real shipped WEEP manifest carried Windows paths.
        "C:/hpi_dev/images/Wave1/Day3/QR",
        "C:\\hpi_dev\\images\\Wave1\\Day3\\QR",
    ],
)
def test_an_absolute_source_scan_path_is_rejected_rather_than_mangled(
    tmp_path, scan_path
):
    """Replaces the `lstrip("./")` character-strip.

    Task 0.9 established Bloom never emits an absolute path, so there is no shipped
    behavior to preserve — but the strip ate a leading separator rather than failing,
    which would have reported every row missing with nothing actually absent.

    The `scans.csv` names the same absolute path so the manifest/scans cross-check passes
    and this guard is the one that fires. Before the blocking review of #40 it was not:
    the cross-check raised first, and the test passed only because `match="absolute"`
    searched a message embedding `tmp_path`, whose basename pytest derives from the test's
    own name.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    write_scans_csv(bloomctl_scans, scan_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", scan_path)

    with pytest.raises(
        ValueError, match="must be relative to the scans.csv directory"
    ) as excinfo:
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")
    assert "source_scan_path" in str(excinfo.value)


@pytest.mark.parametrize(
    "scan_path",
    [
        "D:hpi_dev/images/Wave1/Day3/QR",
        "D:hpi_dev\\images\\Wave1\\Day3\\QR",
        # A bare drive reference, which anchors just as hard as one with a tail.
        "D:",
    ],
)
def test_a_drive_relative_source_scan_path_is_rejected_rather_than_anchoring(
    tmp_path, scan_path
):
    r"""A drive letter with no separator after the colon is not absolute, and still anchors.

    Third blocking review of #40. `D:scan` is *drive-relative*: it means "scan, resolved
    against whatever the process's current directory on drive D happens to be". Windows
    agrees it is not absolute, and so do both flavours — `PureWindowsPath("D:scan")
    .is_absolute()` is False — so it passed the guard added for `C:\scan`. But joining it
    onto a concrete base discards the base outright: `WindowsPath("C:/pkg") / "D:scan"` is
    `D:scan`, not `C:/pkg/D:scan`. A `subst`-mapped drive then reads a file from anywhere
    on the machine into `images/` under a curated name, and the copy reports success --
    the same silent-substitution outcome the absolute and `..` guards exist to prevent.

    The drive is what makes a path anchor, so the drive is what gets checked, rather than
    a definition of "absolute" that Windows and pathlib both read differently here.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    write_scans_csv(bloomctl_scans, scan_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", scan_path)

    with pytest.raises(ValueError, match="names a drive") as excinfo:
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")
    assert "source_scan_path" in str(excinfo.value)
    assert not (tmp_path / "package/images").exists()


def test_a_drive_relative_source_image_is_rejected_even_when_its_scan_resolves(
    tmp_path,
):
    # The same bypass at the per-row guard, which the scan-directory guard never reaches.
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    rows = list(csv.DictReader(manifest.open()))
    for row in rows:
        row["source_image"] = f"D:planted/{Path(row['source_image']).name}"
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="names a drive") as excinfo:
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")
    assert "source_image" in str(excinfo.value)


def test_an_ordinary_relative_path_containing_a_colon_still_copies(tmp_path):
    """The drive check keys on the drive component, not on the colon character.

    A colon anywhere but the second position is an ordinary path character to
    `PureWindowsPath`, and rejecting on the character would have failed real scan
    directories -- accession ids like `PI:594301` are exactly the naming this repo already
    handles elsewhere.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    colon_path = "images/Wave1/Day3_20250101/PI:594301"
    scan_dir = bloomctl_scans.parent / colon_path
    scan_dir.mkdir(parents=True)
    for view_index in range(1, 73):
        (scan_dir / f"{view_index}.jpg").write_bytes(f"jpeg-{view_index}".encode())
    write_scans_csv(bloomctl_scans, colon_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", colon_path)
    images_dir = tmp_path / "package/images"

    assert copy_selected_images(manifest, bloomctl_scans, images_dir) == 3
    assert (images_dir / "A3244_9DK8KJJEZR_age3_1.jpg").read_bytes() == b"jpeg-25"


def test_an_absolute_source_image_is_rejected_even_when_its_scan_resolves(tmp_path):
    # The second guard, on the per-row path rather than the scan directory. Reachable only
    # once the scan directory itself resolves, so the manifest keeps a valid scan path and
    # rewrites just `source_image`.
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    rows = list(csv.DictReader(manifest.open()))
    for row in rows:
        row["source_image"] = f"/etc/{Path(row['source_image']).name}"
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(
        ValueError, match="must be relative to the scans.csv directory"
    ) as excinfo:
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")
    assert "source_image" in str(excinfo.value)


def test_a_traversing_source_image_cannot_read_a_file_from_outside_the_download(
    tmp_path,
):
    """A manifest is an anticipated hand-edited input, and `..` reached anywhere on disk.

    The file arrives in `images/` under a curated name, where nothing downstream can tell
    it from a real scan image.
    """
    bloomctl_scans, _ = build_download(tmp_path)
    secret = tmp_path / "secret.jpg"
    secret.write_bytes(b"not-a-scan")
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    rows = list(csv.DictReader(manifest.open()))
    for row in rows:
        row["source_image"] = "../../../secret.jpg"
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match=r"climbs out of it with '\.\.'"):
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")
    assert not (tmp_path / "package/images").exists()


def test_an_empty_manifest_fails_instead_of_creating_an_empty_images_directory(
    tmp_path,
):
    """RED against the port: this reported `copied 0 image(s)` and exited 0.

    An empty `images/` is indistinguishable from a copy step that has not been run, so the
    next stage cannot tell a finished package from an unstarted one (design.md F1).
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = tmp_path / "sample_manifest.csv"
    with manifest.open("w", newline="") as fh:
        csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS)).writeheader()

    with pytest.raises(ValueError, match="has no rows"):
        copy_selected_images(manifest, bloomctl_scans, tmp_path / "package/images")
    assert not (tmp_path / "package/images").exists()


def test_an_output_filename_that_escapes_the_images_directory_is_rejected(tmp_path):
    """The write side of the same class: `output_filename` reached `shutil.copy2` raw.

    Reproduced in review with `--accession-names '{"111": "../../pwn"}'`, which wrote two
    JPEGs outside the staging directory — where the failure path's `rmtree` could not
    remove them, defeating "nothing lands until everything passes".
    """
    bloomctl_scans, _ = build_download(tmp_path)
    manifest = write_manifest(tmp_path / "sample_manifest.csv", BLOOMCTL_SCAN_PATH)
    rows = list(csv.DictReader(manifest.open()))
    for row in rows:
        row["output_filename"] = f"../../{row['output_filename']}"
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    output_dir = tmp_path / "package/images"
    with pytest.raises(ValueError, match="not plain filenames"):
        copy_selected_images(manifest, bloomctl_scans, output_dir)
    assert not output_dir.exists()
    assert not list(tmp_path.glob("*.jpg"))


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
