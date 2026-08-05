"""Checks a labeling package must pass before it is published.

design.md Decision 2 splits the embed guarantee in two: the builder *performs* embedding, so
the on-disk package is already a complete artifact, and this module *verifies* it — which is
what makes the guarantee a property of the package rather than of the code path that
happened to write it. A package built by an older tool, or assembled by hand, is checked by
the same rule.

``#10``'s ``publish-labels`` calls :func:`validate_package` before any network call — it is
the single entry point that answers "is this directory a labeling package?", and it reads
nothing outside the directory it is given. That last part is Decision 3's "no dependency on
the machine that produced it" made checkable: a validator that resolved ``source_image``
back to the source filesystem would pass only where the package was built, which is the
opposite of the guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import sleap_io as sio

from sleap_roots_training.labeling.metadata import PackageRecord, read_package_metadata
from sleap_roots_training.labeling.select_samples import (
    MANIFEST_COLUMNS,
    assert_unique_output_filenames,
)

#: The manifest's name inside a package. Part of Decision 3's layout contract.
MANIFEST_FILENAME = "sample_manifest.csv"

#: The curated images directory. Task 5.5 keeps it in the package: the spec's one-to-one
#: requirement is checked against it, and ``output_filename`` resolves to nothing without it.
IMAGES_DIRNAME = "images"


def _external_references(slp_path: Path) -> list[str]:
    """Return the external video paths a ``.slp`` depends on.

    A video whose frames are embedded records the ``.slp`` itself as its filename; the
    original paths survive only as ``source_video`` provenance, which nothing needs to
    open. Anything else is a path the package cannot guarantee.

    Args:
        slp_path: Path to the ``.slp`` file.

    Returns:
        The external paths referenced, empty if the file is self-contained.
    """
    # `open_videos=False` so an already-broken package is diagnosable rather than raising
    # on the very dependency being checked.
    labels = sio.load_slp(str(slp_path), open_videos=False)
    external: list[str] = []
    for video in labels.videos:
        filenames = (
            video.filename if isinstance(video.filename, list) else [video.filename]
        )
        if any(Path(name) != Path(slp_path) for name in filenames):
            external.extend(str(name) for name in filenames)
    return external


def slp_is_self_contained(slp_path: Path) -> bool:
    """Return whether a ``.slp`` carries its own images.

    Args:
        slp_path: Path to the ``.slp`` file.

    Returns:
        ``True`` if no video references a path outside the file itself.
    """
    return not _external_references(slp_path)


def assert_slp_is_self_contained(slp_path: Path) -> None:
    """Fail if a ``.slp`` depends on images stored outside it.

    Args:
        slp_path: Path to the ``.slp`` file.

    Raises:
        ValueError: If any video references an external path, naming the file and the
            paths it depends on.
    """
    external = _external_references(slp_path)
    if not external:
        return
    listed = "\n  ".join(external[:10])
    more = f"\n  ... and {len(external) - 10} more" if len(external) > 10 else ""
    raise ValueError(
        f"{slp_path} is not self-contained: it references {len(external)} image path(s) "
        f"outside itself:\n  {listed}{more}\nA package like this breaks when those paths "
        "become unreachable, and the standard repair — re-saving the embedded subset — "
        "permanently caps the label set at whatever was embedded at repair time. Rebuild "
        "it rather than publishing it."
    )


def project_filename(record: PackageRecord, root_type: str) -> str:
    """Return the ``.slp`` filename a package's root type is written under.

    The builder's naming, stated once so validation looks for the same file the builder
    wrote rather than for a glob that would accept a near-miss.

    Args:
        record: The package record.
        root_type: The root type.

    Returns:
        The filename, e.g. ``soybean_weep_primary_labels.v000.slp``.
    """
    meta = record.metadata
    return f"{meta.species}_{meta.experiment}_{root_type}_labels.{record.version}.slp"


def _assert_layout(package_dir: Path, record: PackageRecord) -> dict[str, Path]:
    """Check every piece of the layout is present, naming whichever is not.

    Args:
        package_dir: The package directory.
        record: The package record, which declares what must be there.

    Returns:
        The project path for each declared root type.

    Raises:
        ValueError: If the manifest, the images directory, or a declared root type's
            project file is missing.
    """
    if not (package_dir / MANIFEST_FILENAME).is_file():
        raise ValueError(
            f"{package_dir} has no {MANIFEST_FILENAME}. Decision 3 makes the manifest "
            "part of the package: it is the row-level provenance that travels inside the "
            "artifact, so a package without one cannot say which scans it came from."
        )
    if not (package_dir / IMAGES_DIRNAME).is_dir():
        raise ValueError(
            f"{package_dir} has no {IMAGES_DIRNAME}/ directory. It is what the manifest's "
            "`output_filename` column names, and what a reviewer browses without "
            "installing SLEAP."
        )
    projects = {}
    for root_type in record.metadata.root_types:
        path = package_dir / project_filename(record, root_type)
        if not path.is_file():
            raise ValueError(
                f"{package_dir} declares root type {root_type!r} but has no "
                f"{path.name}. A declared root type with no project file is a package "
                "that promises labels it does not carry."
            )
        projects[root_type] = path
    return projects


def _assert_manifest_columns(manifest: pd.DataFrame) -> None:
    """Fail if the manifest lacks a column Decision 3 enumerates, naming it.

    Args:
        manifest: The loaded manifest.

    Raises:
        ValueError: If any required column is absent.
    """
    absent = [column for column in MANIFEST_COLUMNS if column not in manifest.columns]
    if absent:
        raise ValueError(
            f"{MANIFEST_FILENAME} is missing required column(s) {absent}. The enumerated "
            "columns are what let a consumer recover the exact scans, plants, and "
            "accessions from the artifact alone, without the source filesystem."
        )


def assert_counts_agree(
    package_dir: Path, manifest: pd.DataFrame, record: PackageRecord
) -> None:
    """Fail if the declared count, the manifest, and the curated images disagree.

    Three numbers that must be one number. The README used to report a fourth, globbed
    from ``images/`` (design.md F7), so a dropped image surfaced as smaller prose in the
    documentation and nowhere a machine could see it.

    Public because :mod:`sleap_roots_training.labeling.render_readme` runs the same rule
    before it publishes any of these numbers to a human. One rule with two callers, the
    way ``assert_unique_output_filenames`` is shared between selection and the copy step
    (task 3.5) — two rules that agree today are two rules that can drift.

    Args:
        package_dir: The package directory.
        manifest: The loaded manifest.
        record: The package record.

    Raises:
        ValueError: If the manifest is empty, if the declared frame count disagrees with
            the manifest row count, or if the curated images do not correspond one-to-one
            with the manifest rows.
    """
    rows = len(manifest)
    if rows == 0:
        raise ValueError(
            f"{MANIFEST_FILENAME} has no rows, so the package holds no labeled frames. "
            "An empty package that reports success is the failure this validation exists "
            "for (design.md F1)."
        )
    if record.frame_count != rows:
        raise ValueError(
            f"package metadata declares frame_count={record.frame_count} but "
            f"{MANIFEST_FILENAME} has {rows} row(s). One of them is wrong, and a "
            "consumer cannot tell which."
        )

    images_dir = package_dir / IMAGES_DIRNAME
    on_disk = {path.name for path in images_dir.iterdir() if path.is_file()}
    named = set(manifest["output_filename"])
    if len(on_disk) != rows:
        raise ValueError(
            f"{IMAGES_DIRNAME}/ holds {len(on_disk)} file(s) but {MANIFEST_FILENAME} has "
            f"{rows} row(s). Every row corresponds to exactly one curated image and every "
            "curated image to exactly one row."
        )
    absent = sorted(named - on_disk)
    if absent:
        listed = "\n  ".join(absent[:10])
        more = f"\n  ... and {len(absent) - 10} more" if len(absent) > 10 else ""
        raise ValueError(
            f"{len(absent)} manifest row(s) name a curated image that is not in "
            f"{IMAGES_DIRNAME}/:\n  {listed}{more}"
        )
    unclaimed = sorted(on_disk - named)
    if unclaimed:
        listed = "\n  ".join(unclaimed[:10])
        more = f"\n  ... and {len(unclaimed) - 10} more" if len(unclaimed) > 10 else ""
        raise ValueError(
            f"{len(unclaimed)} file(s) in {IMAGES_DIRNAME}/ are named by no manifest row:"
            f"\n  {listed}{more}"
        )


def _assert_skeleton_matches_record(
    slp_path: Path, root_type: str, recorded: tuple[str, ...]
) -> None:
    """Fail if the project's skeleton is not the one the metadata records.

    Task 8.3c. The node counts lived in two hand-synced places — prose in
    ``generate_readme.py`` and constants in ``build_slp_project.py`` — and nothing
    compared them, which is how ``docs/roadmap.md:201`` ends up recording them as unknown
    for the published collections. The record is now the single source the README renders
    from, so this is the check that keeps it honest about the file beside it.

    Args:
        slp_path: Path to the project file.
        root_type: The root type it holds.
        recorded: The node names the metadata records.

    Raises:
        ValueError: If the project has no skeleton, more than one, or a different one.
    """
    labels = sio.load_slp(str(slp_path), open_videos=False)
    if len(labels.skeletons) != 1:
        raise ValueError(
            f"{slp_path.name} has {len(labels.skeletons)} skeletons, expected exactly one "
            f"for root type {root_type!r}."
        )
    actual = tuple(labels.skeletons[0].node_names)
    if actual != tuple(recorded):
        raise ValueError(
            f"package metadata records the {root_type!r} skeleton as {list(recorded)} "
            f"but {slp_path.name} carries {list(actual)}. The metadata is what a consumer "
            "reads instead of opening the file, so the two disagreeing makes it worse "
            "than absent."
        )


def validate_package(package_dir: Path) -> PackageRecord:
    """Check a directory is a publishable labeling package.

    Task 8.1 — the one callable ``#10``'s ``publish-labels`` runs before any network call.
    Reads only what is inside ``package_dir``, so a valid package validates wherever it is
    delivered rather than only where it was produced.

    Args:
        package_dir: The package directory.

    Returns:
        The package's validated metadata record.

    Raises:
        FileNotFoundError: If the package metadata file is absent.
        ValueError: If the layout, the manifest's columns, the counts, the skeletons, or
            the embedding guarantee fail, naming the offending piece in each case.
    """
    package_dir = Path(package_dir)
    # Metadata first: it declares the root types, so it is what says which project files
    # must exist. Everything below is checked against what the package claims to be.
    record = read_package_metadata(package_dir)
    projects = _assert_layout(package_dir, record)

    manifest = pd.read_csv(package_dir / MANIFEST_FILENAME)
    _assert_manifest_columns(manifest)
    assert_unique_output_filenames(manifest)
    assert_counts_agree(package_dir, manifest, record)

    for root_type, path in projects.items():
        _assert_skeleton_matches_record(path, root_type, record.skeletons[root_type])
        assert_slp_is_self_contained(path)
    return record
