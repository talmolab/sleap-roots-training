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
from pathlib import Path, PurePosixPath

import pandas as pd

from sleap_roots_training.labeling.select_samples import (
    TOTAL_VIEWS,
    assert_unique_output_filenames,
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


def _posix(path: object) -> PurePosixPath:
    """Normalize a manifest or ``scans.csv`` path to POSIX form.

    Args:
        path: A path as written by either producer, possibly with backslash separators
            from a Windows run or a ``./`` prefix from the legacy Bloom CLI.

    Returns:
        The normalized relative path. ``PurePosixPath`` collapses a leading ``./``.
    """
    return PurePosixPath(str(path).replace("\\", "/"))


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
        ValueError: If ``source_scan_path`` is absolute.
    """
    relative = _posix(source_scan_path)
    if relative.is_absolute():
        raise ValueError(
            f"source_scan_path must be relative to the scans.csv directory, got the "
            f"absolute path {str(relative)!r}. Bloom does not emit absolute paths; an "
            "absolute one means the manifest was hand-edited or rewritten."
        )
    return base / relative


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
        ValueError: If the manifest lacks a required column, assigns one
            ``output_filename`` to two frames, names a scan ``scans.csv`` does not
            describe, carries an absolute path, or points at a scan whose view count
            contradicts ``total_views``.
        FileNotFoundError: If any scan directory or source image does not exist.
    """
    manifest = pd.read_csv(manifest_csv)
    _assert_required_columns(manifest)
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
        source = _posix(row.source_image)
        if source.is_absolute():
            raise ValueError(
                f"source_image must be relative to the scans.csv directory, got the "
                f"absolute path {str(source)!r} for {row.output_filename!r}."
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

    output_dir.mkdir(parents=True, exist_ok=True)
    for src, output_filename in planned:
        shutil.copy2(src, output_dir / output_filename)

    logger.info("Copied %d images to %s", len(planned), output_dir)
    return len(planned)
