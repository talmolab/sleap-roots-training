"""Gather each selected frame's image under its curated name.

Ported from the vault workflow's ``copy_selected_images.py`` (talmolab/sleap-roots-training#26;
Box copy 2026-08-03). This is the bridge between the two names a manifest row carries:
:mod:`~sleap_roots_training.labeling.select_samples` writes ``source_image`` — the real path
inside the downloaded scan — and ``output_filename`` — the curated name the builder reads out
of ``images/``. Nothing else connects them.

The step is **all-or-nothing** (task 3.4). Every row is resolved and checked before a single
file is written, so a run either populates ``images/`` completely or leaves nothing behind.
The vault script instead warned per row and returned normally, which — composed with the
builder doing the same — turned an entirely unreachable source into two rounds of warnings, a
zero exit, and an empty package (design.md F5). Its faithful behavior is in this file's first
commit; the tests name what each deviation replaced.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import pandas as pd

from sleap_roots_training.labeling.layout import is_sidecar
from sleap_roots_training.labeling.select_samples import (
    TOTAL_VIEWS,
    assert_unique_output_filenames,
    posix_path as _posix,
)

logger = logging.getLogger(__name__)

#: Manifest columns this step reads. Deliberately narrower than ``MANIFEST_COLUMNS`` —
#: validating the whole package contract is :mod:`validate`'s job (task 8.1), and a step
#: that rejects a manifest over a column it never touches is a step that fails for the
#: wrong reason.
REQUIRED_COLUMNS = (
    "scan_id",
    "source_scan_path",
    "source_image",
    "output_filename",
)


def _assert_contained_relative(
    path: object, column: str, output_filename: object
) -> PurePosixPath:
    r"""Normalize a manifest path and fail unless it stays under the base directory.

    Deviation (blocking review of #40). The guard this replaces normalized to
    ``PurePosixPath`` and then asked ``.is_absolute()`` — which is ``False`` for
    ``C:\data\scan1``, because a drive letter is only absolute to
    ``PureWindowsPath``. A Windows absolute path therefore slipped past the rejection and
    was joined onto the base anyway, resolving against something arbitrary while the
    operator was told paths resolve "against the directory holding scans.csv". design.md
    F11 records that the real shipped WEEP manifest carried Windows paths, so this
    producer is observed rather than hypothetical.

    ``..`` is rejected for the same reason the absolute case is: manifests are an
    anticipated hand-edited and reused input (this module's own docstring), and a ``..``
    segment reads a file from anywhere on the filesystem into the package under a curated
    name, where nothing downstream can tell it apart from a real scan image.

    Args:
        path: The manifest cell's value.
        column: The column it came from, for the error message.
        output_filename: The row's curated name, for the error message.

    Returns:
        The normalized relative path.

    Raises:
        ValueError: If the path is absolute in either convention, or escapes the base.
    """
    text = str(path).replace("\\", "/")
    relative = PurePosixPath(text)
    if relative.is_absolute() or PureWindowsPath(text).is_absolute():
        raise ValueError(
            f"{column} must be relative to the scans.csv directory, got the absolute "
            f"path {text!r} for {output_filename!r}. Bloom does not emit absolute paths; "
            "an absolute one means the manifest was hand-edited or rewritten, and it "
            "would resolve against a directory this package knows nothing about."
        )
    if ".." in relative.parts:
        raise ValueError(
            f"{column} must stay under the scans.csv directory, got {text!r} for "
            f"{output_filename!r}, which climbs out of it with '..'. A row that reaches "
            "outside the download reads an arbitrary file into the package under a "
            "curated name, where nothing downstream can tell it from a real scan image."
        )
    return relative


def _assert_required_columns(manifest: pd.DataFrame) -> None:
    """Fail if the manifest lacks a column this step reads.

    Args:
        manifest: The loaded manifest.

    Raises:
        ValueError: If any required column is absent, naming the missing columns.
    """
    absent = [column for column in REQUIRED_COLUMNS if column not in manifest.columns]
    if absent:
        raise ValueError(
            f"sample_manifest.csv is missing required column(s): {', '.join(absent)}"
        )


def _assert_manifest_came_from_these_scans(
    manifest: pd.DataFrame, scans_csv: Path
) -> None:
    """Fail if the manifest's scans are not the ones this ``scans.csv`` describes.

    This is what makes the resolution rule safe rather than merely explicit. The base
    directory is derived from ``scans_csv``, so pointing at the wrong ``scans.csv``
    reintroduces design.md F8 one layer up — every row resolving nowhere, with correct
    data. Checking that each manifest row's ``(scan_id, source_scan_path)`` pair is
    actually in this file turns that into a named error instead of an empty package.

    Args:
        manifest: The loaded manifest.
        scans_csv: The ``scans.csv`` the manifest's paths are relative to.

    Raises:
        ValueError: If ``scans.csv`` lacks the columns needed to check, or if any
            manifest row names a scan it does not describe.
    """
    scans = pd.read_csv(scans_csv)
    absent = [c for c in ("scan_id", "scan_path") if c not in scans.columns]
    if absent:
        raise ValueError(
            f"{scans_csv} is not a Bloom scans.csv: missing column(s) "
            f"{', '.join(absent)}. It must be the scans.csv the manifest was selected "
            "from, because the manifest's paths are relative to the directory holding it."
        )

    known = {(row.scan_id, str(_posix(row.scan_path))) for row in scans.itertuples()}
    unknown = sorted(
        {
            (row.scan_id, str(_posix(row.source_scan_path)))
            for row in manifest.itertuples()
        }
        - known
    )
    if unknown:
        listed = "; ".join(f"scan_id {sid} at {path!r}" for sid, path in unknown[:5])
        raise ValueError(
            f"{len(unknown)} scan(s) in the manifest are not described by {scans_csv}: "
            f"{listed}. Pass the scans.csv this manifest was selected from — its "
            "directory is the base every source_image is resolved against."
        )


def _scan_directory(base: Path, source_scan_path: object) -> Path:
    """Resolve one scan's directory against the base.

    Args:
        base: The directory holding ``scans.csv``.
        source_scan_path: The manifest row's ``source_scan_path``.

    Returns:
        The scan directory.

    Raises:
        ValueError: If ``source_scan_path`` is absolute or climbs out of ``base``.
    """
    return base / _assert_contained_relative(
        source_scan_path, "source_scan_path", source_scan_path
    )


def _assert_scan_holds_the_assumed_views(scan_dir: Path, total_views: int) -> None:
    """Fail if a scan does not hold the number of views selection assumed.

    Obligation from task 2.5. Selection reads only CSVs, so it cannot check
    ``total_views`` against reality; this is the first stage that sees the images. A
    scan captured at a different view count still selects *plausible* indices — they
    are simply the wrong angles, and the rows for indices past the end point at files
    that do not exist. Caught here, that reports as one wrong parameter; caught by the
    per-row check below, it reports as N unrelated missing files.

    Args:
        scan_dir: The resolved scan directory.
        total_views: The rotational view count selection assumed.

    Raises:
        FileNotFoundError: If the scan directory does not exist.
        ValueError: If the number of view images present differs from ``total_views``.
    """
    if not scan_dir.is_dir():
        raise FileNotFoundError(
            f"Scan directory does not exist: {scan_dir}. It is resolved against the "
            "directory holding scans.csv."
        )
    present = sum(1 for image in scan_dir.glob("*.jpg") if image.stem.isdigit())
    if present != total_views:
        raise ValueError(
            f"{scan_dir} holds {present} rotational view image(s), but selection "
            f"assumed total_views={total_views}. The view indices in the manifest were "
            "computed against that assumption, so they name the wrong angles. Re-run "
            f"selection with total_views={present}."
        )


def copy_selected_images(
    manifest_csv: Path,
    scans_csv: Path,
    output_dir: Path,
    total_views: int = TOTAL_VIEWS,
) -> int:
    """Copy every manifest row's source image into the curated images directory.

    Deviation (task 3.4). Two changes, both making silence impossible:

    **Resolution.** ``source_image`` is resolved against *the directory containing the
    ``scans.csv`` it was derived from*, replacing the vault script's ``experiment_dir``
    join and its ``lstrip("./")`` character-strip. This is producer-agnostic: it
    resolves ``bloomctl``'s convention and the legacy CLI's without detecting which is
    in play, because each producer's paths are relative to its own ``scans.csv``
    (design.md F8). Task 7.2 records why the base arrives as ``scans.csv`` rather than
    as a manifest column or a free directory argument.

    **Failure.** Any unresolved source fails the step, and nothing is written until
    every row has resolved — an empty or partial ``images/`` is never a success
    (design.md F5).

    Args:
        manifest_csv: Path to ``sample_manifest.csv``.
        scans_csv: Path to the ``scans.csv`` this manifest was selected from. Its
            directory is the base every ``source_image`` resolves against.
        output_dir: Destination ``images/`` directory.
        total_views: Rotational views a scan is expected to hold, which must match the
            value selection ran with.

    Returns:
        The number of images copied, which equals the manifest row count.

    Raises:
        ValueError: If the manifest is empty, lacks a required column, assigns one
            ``output_filename`` to two frames, names a scan ``scans.csv`` does not
            describe, carries an absolute or ``..``-bearing path, points at a scan whose
            view count contradicts ``total_views``, or if ``output_dir`` holds anything
            this step did not write.
        FileNotFoundError: If any scan directory or source image does not exist.
    """
    manifest = pd.read_csv(manifest_csv)
    _assert_required_columns(manifest)
    if manifest.empty:
        raise ValueError(
            f"{Path(manifest_csv).name} has no rows, so there is nothing to copy. "
            "Creating an empty images/ and reporting success is design.md F1 — the next "
            "stage cannot distinguish it from a copy that has not been run yet. Re-run "
            "selection; a header-only manifest means its inputs did not overlap."
        )
    assert_unique_output_filenames(manifest)

    base = Path(scans_csv).parent
    _assert_manifest_came_from_these_scans(manifest, scans_csv)

    for scan_path in manifest["source_scan_path"].unique():
        _assert_scan_holds_the_assumed_views(
            _scan_directory(base, scan_path), total_views
        )

    # Resolve every row before writing anything, so a failure leaves no directory a
    # later stage could mistake for a completed copy.
    planned: list[tuple[Path, str]] = []
    unresolved: list[str] = []
    for row in manifest.itertuples():
        source = _assert_contained_relative(
            row.source_image, "source_image", row.output_filename
        )
        src = base / source
        if not src.exists():
            unresolved.append(f"{row.output_filename!r} -> {src}")
            continue
        planned.append((src, str(row.output_filename)))

    if unresolved:
        listed = "\n  ".join(unresolved[:10])
        more = (
            f"\n  ... and {len(unresolved) - 10} more" if len(unresolved) > 10 else ""
        )
        raise FileNotFoundError(
            f"{len(unresolved)} of {len(manifest)} manifest row(s) name a source image "
            f"that does not exist under {base}:\n  {listed}{more}"
        )

    # Deviation (blocking review of #40): the loop is transactional. It used to write
    # straight into `output_dir`, so any mid-loop `OSError` — ENOSPC, a Box or NFS mount
    # dropping, a permissions change — left a partial `images/` behind, contradicting this
    # module's own all-or-nothing docstring and the CLI help. Re-running merged into it
    # (`exist_ok=True`), so the orphans surfaced much later as a counts mismatch that
    # blamed the manifest. Files land in a staging directory beside the destination — same
    # filesystem, so the rename is atomic — and are moved into place only once every copy
    # has succeeded.
    # Re-running stays idempotent, and is now more so: the destination is *replaced*
    # rather than merged into, so a file left by an earlier run with different parameters
    # does not survive to surface later as a counts mismatch blaming the manifest.
    output_dir = Path(output_dir)
    _assert_safe_to_replace(output_dir, {name for _, name in planned})
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(dir=output_dir.parent, prefix=f"{output_dir.name}.partial-")
    )
    try:
        staging.chmod(0o755)
        for src, output_filename in planned:
            shutil.copy2(src, staging / output_filename)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    _replace_directory(staging, output_dir)
    logger.info("Copied %d images to %s", len(planned), output_dir)
    return len(planned)


def _assert_safe_to_replace(output_dir: Path, planned_names: set[str]) -> None:
    """Fail unless replacing ``output_dir`` wholesale can only destroy this step's output.

    Replacing the destination is what keeps a re-run from inheriting an earlier run's
    orphans, but ``--output-dir`` is a free path from the CLI, so a mistyped or misaimed
    value would otherwise hand an arbitrary directory tree to ``shutil.rmtree`` (blocking
    review of #40, second pass). This module is scrupulous about exactly this class on the
    read side — see :func:`_assert_contained_relative` and
    ``assert_unique_output_filenames`` — and the write side had no equivalent.

    A destination is safe when it does not exist, is empty, or looks like an images
    directory: flat, and holding nothing but ``.jpg`` files and operating-system sidecars.
    That still lets a re-run clear an earlier run's orphans — the whole point of replacing
    rather than merging, and a file the previous parameters produced is not one this run
    will write — while refusing to delete a directory holding anything that is not a
    curated frame.

    Args:
        output_dir: The destination.
        planned_names: The curated filenames this run will write. Any of these is safe by
            definition; the check is about everything *else* in the directory.

    Raises:
        ValueError: If the destination holds anything that is not a curated image.
    """
    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise ValueError(
            f"{output_dir} is not a directory. --output-dir names the images directory a "
            "package's curated frames go in."
        )

    def is_curated(entry: Path) -> bool:
        if not entry.is_file():
            return False
        return (
            entry.name in planned_names
            or is_sidecar(entry.name)
            or entry.suffix.lower() == ".jpg"
        )

    unexpected = sorted(
        entry.name for entry in output_dir.iterdir() if not is_curated(entry)
    )
    if unexpected:
        listed = ", ".join(repr(name) for name in unexpected[:5])
        more = f" ... and {len(unexpected) - 5} more" if len(unexpected) > 5 else ""
        raise ValueError(
            f"{output_dir} holds {len(unexpected)} entr(y/ies) that are not curated "
            f"images: {listed}{more}. The copy step replaces its destination rather than "
            "merging into it, so it refuses to delete a directory that holds anything "
            "else — --output-dir is a free path, and a mistyped one would otherwise take "
            "an arbitrary directory tree with it. Point it at the package's images "
            "directory, or remove that directory by hand if you do mean to discard it."
        )


def _replace_directory(staging: Path, output_dir: Path) -> None:
    """Move ``staging`` onto ``output_dir``, without a window where neither exists.

    The obvious spelling — ``rmtree(output_dir)`` then ``rename`` — is two syscalls, and a
    crash between them leaves the destination *deleted* while the finished copy sits beside
    it under a temporary name. This module reasons about SIGKILL elsewhere (an OOM runs no
    cleanup handler), so that window is not hypothetical, and losing an existing ``images/``
    to a re-run that was going to replace it anyway is the worst possible outcome.

    Renaming the old directory aside first means the destination is only ever the old
    contents or the new ones. The stale copy is removed last, when nothing depends on it.

    Args:
        staging: The fully populated staging directory.
        output_dir: Where it should end up.
    """
    if not output_dir.exists():
        staging.rename(output_dir)
        return
    # `mkdtemp` reserves a name that is guaranteed free, then releases it: `Path.rename`
    # will not overwrite an existing directory on Windows, so the target has to be absent.
    superseded = Path(
        tempfile.mkdtemp(dir=output_dir.parent, prefix=f"{output_dir.name}.superseded-")
    )
    superseded.rmdir()
    output_dir.rename(superseded)
    try:
        staging.rename(output_dir)
    except BaseException:
        superseded.rename(output_dir)
        raise
    shutil.rmtree(superseded, ignore_errors=True)
    if superseded.exists():
        logger.warning(
            "Could not remove the superseded images directory %s. It is a complete copy "
            "of the previous run's output and nothing else will clean it up.",
            superseded,
        )
