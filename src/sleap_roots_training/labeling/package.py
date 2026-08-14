"""Assemble a complete labeling package, all-or-nothing.

Task 8.4. The four stages each fail loudly on their own — selection (section 2), the image
copy (section 3), the builder (sections 4–6), and validation (8.1) — but a package is only
a package once all of them have run and agreed. This module runs them in order and is
where Decision 3's layout stops being a description and becomes a property.

**Nothing lands until everything passes.** The package is assembled in a staging directory
beside the destination, validated there, and moved into place only once it is complete;
the destination does not exist until then, and the staging directory is removed on any
failure. This is task 4.7's rule raised a level. The builder already refuses to write a
partial *project*, but "the run died between the copy step and the build" produces exactly
the same artifact F1 describes — a directory that looks like a package and is not — and a
later step cannot tell the two apart.

The stages stay separate modules (task 3.6): the copy step is the only one that knows
Bloom's download layout, and the builder knows nothing beyond a manifest and a directory of
curated names. This is the one place that knows both, which is what an orchestrator is for.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from sleap_roots_training.labeling.build_package import (
    assert_buildable_manifest,
    build_slp_project,
    prediction_models,
    skeleton_for,
)
from sleap_roots_training.labeling.copy_images import copy_selected_images
from sleap_roots_training.labeling.metadata import (
    PackageMetadata,
    PackageRecord,
    Provenance,
    SelectionParameters,
    write_package_metadata,
)
from sleap_roots_training.labeling.skeletons import skeleton_table_sha256
from sleap_roots_training.registry.lineage import resolve_git_sha
from sleap_roots_training.labeling.layout import IMAGES_DIRNAME, MANIFEST_FILENAME
from sleap_roots_training.labeling.render_readme import render_readme
from sleap_roots_training.labeling.validate import validate_package

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    """Return the hex SHA256 of a file's bytes, read in chunks.

    Args:
        path: The file to hash.

    Returns:
        The hex digest.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_provenance(
    manifest_csv: Path,
    scans_csv: Path,
    manifest: pd.DataFrame,
    predictions_dir: Path,
    root_types: Sequence[str],
) -> Provenance:
    """Record what this package was derived from, so it can be re-derived honestly.

    New in the blocking review of #40. The recorded :class:`SelectionParameters` make a
    package reproducible only against a byte-identical pool, and the usual reason to
    re-derive one is that the pool has changed — new waves landed. Without the inputs'
    identity in the artifact, "re-derive with the same seed" silently produces a different,
    non-superset selection and nothing can tell.

    What is recorded: the ``scans.csv`` bytes (the scan pool), the manifest bytes (the exact
    selection), the skeleton table bytes, and the code version.

    What is **not**, and it is the one that matters most: the QC-cleaned pool. It decides
    which plants were eligible, it changes independently of ``scans.csv``, and this stage
    never sees it — ``--cleaned-csv`` is a ``select`` option, and it may be a glob over
    several files that no single path identifies. :attr:`Provenance.manifest_sha256`
    documents the gap. Hashing the manifest *into a field named for the QC pool* was the
    first attempt and is strictly worse than leaving it out, because a consumer checking
    their own QC table would get a guaranteed mismatch.

    Args:
        manifest_csv: The manifest the package was built from.
        scans_csv: The ``scans.csv`` the manifest was selected from.
        manifest: The loaded manifest, for resolving which prediction files were read.
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory.
        root_types: The root types the package declares.

    Returns:
        The provenance record.
    """
    return Provenance(
        scans_csv_sha256=_sha256(Path(scans_csv)),
        manifest_sha256=_sha256(Path(manifest_csv)),
        skeleton_table_sha256=skeleton_table_sha256(),
        # The same resolver the model registry stamps its seed runs with: explicit env
        # override, then `git rev-parse` anchored at the package (with `+dirty`), then the
        # installed version, then "unknown". Never raises.
        code_version=resolve_git_sha(),
        prediction_models=prediction_models(
            manifest, Path(predictions_dir), root_types
        ),
    )


def _assert_selection_could_have_produced(
    manifest: pd.DataFrame, selection: SelectionParameters
) -> None:
    """Fail if the recorded parameters contradict the manifest they claim to describe.

    The parameters are supplied again at build time, so they can be supplied wrongly, and
    a recorded seed that did not produce the package is worse than no seed at all: it
    invites a re-derivation that silently yields a different label set, which is the
    failure Decision 5 exists to prevent. The manifest cannot confirm a seed — that is
    what determinism is for — but it can contradict ``views_per_plant``, which is the
    parameter a caller is most likely to change between selection and build.

    The invariant is per **scan**, not per plant (deviation, blocking review of #40).
    Selection emits exactly ``len(selected_views)`` rows per scan row and filters on
    barcode alone, so a plant scanned at two ages legitimately carries
    ``2 x views_per_plant`` rows. Grouping by ``plant_qr_code`` therefore rejected the
    selector's own output for any longitudinal experiment — the normal shape of this data,
    which is why ``output_filename`` embeds the age at all and why ``--cleaned-csv`` takes
    a glob spanning per-age QC files. The message it produced was actively wrong: those
    parameters *did* produce that manifest.

    Args:
        manifest: The loaded manifest.
        selection: The parameters being recorded.

    Raises:
        ValueError: If any scan carries more views than ``views_per_plant`` allows.
    """
    per_scan = manifest.groupby("scan_id").size()
    most = int(per_scan.max())
    if most > selection.views_per_plant:
        crowded = sorted(per_scan[per_scan > selection.views_per_plant].index)
        raise ValueError(
            f"selection parameter 'views_per_plant' is {selection.views_per_plant}, but "
            f"{MANIFEST_FILENAME} gives up to {most} views to a single scan "
            f"(scan_ids {crowded[:5]}). These parameters did not produce this manifest, "
            "so recording them would make the package's own re-derivation instructions "
            "wrong. Note the invariant is per scan: a plant scanned at several ages "
            "carries that many times views_per_plant rows, which is expected."
        )


def build_labeling_package(
    manifest_csv: Path,
    scans_csv: Path,
    predictions_dir: Path,
    output_dir: Path,
    metadata: PackageMetadata,
    *,
    bloom_experiment_id: int,
    accessions: Mapping[str, str],
    selection: SelectionParameters,
    version: str = "v000",
) -> Path:
    """Build a complete, validated labeling package at ``output_dir``.

    Args:
        manifest_csv: The ``sample_manifest.csv`` selection produced.
        scans_csv: The ``scans.csv`` that manifest was selected from. Its directory is the
            base every ``source_image`` resolves against (task 7.2).
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory.
        output_dir: Where the package goes. Must not already exist.
        metadata: The package's identity.
        bloom_experiment_id: The Bloom experiment the scans came from.
        accessions: Map of ``accession_id`` to accession name, looked up from Bloom by
            hand (design.md F2).
        selection: The parameters selection ran with, recorded so the package can be
            re-derived and widened (Decision 6).
        version: Version string for the output filenames.

    Returns:
        The package directory.

    Raises:
        ValueError: If ``output_dir`` already exists, if the recorded selection
            parameters contradict the manifest, or if any stage rejects its inputs.
        FileNotFoundError: If a source image or curated image cannot be resolved.
    """
    manifest_csv = Path(manifest_csv)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError(
            f"{output_dir} already exists. A package version is an immutable snapshot "
            "(the v000/v001 convention the README documents), so building into an "
            "existing directory would leave an earlier run's files inside this one. "
            "Remove it, or build the next version elsewhere."
        )

    manifest = pd.read_csv(manifest_csv)
    # Before the selection cross-check, not after (suggestion, third review of #40). Both
    # guards were individually right and their *order* was not: a manifest that was empty
    # from the start -- reused from an earlier run, hand-written, or written by a tool that
    # is not this selector -- reached `int(per_scan.max())` on an empty Series and died as
    # `cannot convert float NaN to integer`. That is a real refusal arriving by accident,
    # under a message naming nothing an operator can act on, while the check that says the
    # useful thing sat one stage further down in `build_slp_project`. Selection and the
    # copy step reject an empty selection at their own entrances; this is the third
    # entrance, and the only one that does not go through either.
    assert_buildable_manifest(manifest, manifest_csv)
    _assert_selection_could_have_produced(manifest, selection)
    ages = sorted({int(age) for age in manifest["plant_age_days"]})
    # Derived from the committed table rather than read back out of the .slp the builder
    # just wrote: the record has to be an independent statement of the skeleton, or
    # `validate_package`'s check that the two agree compares a thing with itself.
    skeletons = {
        root_type: tuple(skeleton_for(metadata.species, root_type, ages).node_names)
        for root_type in metadata.root_types
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # Not dot-prefixed (deviation, blocking review of #40). The leading dot hid the staging
    # directory from `ls`, so when cleanup could not remove it — a failed rename, a Windows
    # file lock, an OOM kill, which is SIGKILL and runs no handler — a full package's worth
    # of bytes sat there invisibly and nothing ever swept it. A visible name is what makes
    # a leak findable.
    staging = Path(
        tempfile.mkdtemp(dir=output_dir.parent, prefix=f"{output_dir.name}.partial-")
    )
    # `mkdtemp` creates 0700, which the package would inherit through the rename. The
    # package is a handoff — it gets copied to Box and read by someone else — so it should
    # not arrive with permissions that say otherwise. No-op on Windows.
    staging.chmod(0o755)
    try:
        copy_selected_images(
            manifest_csv,
            scans_csv,
            staging / IMAGES_DIRNAME,
            total_views=selection.total_views,
        )
        shutil.copy2(manifest_csv, staging / MANIFEST_FILENAME)
        build_slp_project(
            staging / MANIFEST_FILENAME,
            staging / IMAGES_DIRNAME,
            Path(predictions_dir),
            staging,
            metadata,
            version=version,
        )
        write_package_metadata(
            PackageRecord(
                metadata=metadata,
                bloom_experiment_id=bloom_experiment_id,
                accessions=accessions,
                selection=selection,
                frame_count=len(manifest),
                skeletons=skeletons,
                version=version,
                provenance=build_provenance(
                    manifest_csv,
                    scans_csv,
                    manifest,
                    Path(predictions_dir),
                    metadata.root_types,
                ),
            ),
            staging,
        )
        render_readme(staging)
        validate_package(staging)
        # The move is inside the `try` (deviation, blocking review of #40). It used to sit
        # after it, so a rename that failed — an `ENOTEMPTY` from a destination that
        # appeared while the build ran, a Windows handle still open on a `.slp` — left a
        # complete package's worth of bytes in the staging directory with nothing to remove
        # it and nothing that would ever find it.
        _move_into_place(staging, output_dir)
    except BaseException:
        # Including KeyboardInterrupt: a package half-written by an interrupted run is
        # the same artifact as one half-written by a crash.
        _discard(staging)
        raise

    logger.info("Built labeling package: %s", output_dir)
    return output_dir


def _move_into_place(staging: Path, output_dir: Path) -> None:
    """Move the validated staging directory to its final name.

    ``Path.rename`` replaces an empty destination directory silently on POSIX, so a
    destination that appeared between this build's up-front check and now would be
    absorbed without a word (blocking review of #40). The package is an immutable
    versioned snapshot, so that is checked again here rather than assumed.

    Args:
        staging: The validated staging directory.
        output_dir: Where the package goes.

    Raises:
        ValueError: If the destination exists.
        OSError: If the move fails for any other reason.
    """
    if output_dir.exists():
        raise ValueError(
            f"{output_dir} appeared while this package was being built, so the completed "
            "package was not moved into place. A package version is an immutable "
            "snapshot; two runs writing the same version is a mistake in one of them."
        )
    staging.rename(output_dir)


def _discard(staging: Path) -> None:
    """Remove a staging directory, saying so if it cannot be removed.

    ``ignore_errors=True`` alone swallowed the failure with no log line (blocking review of
    #40) — on Windows a still-open ``.slp`` handle is enough — leaving a package's worth of
    bytes behind and no record that it happened.

    Args:
        staging: The staging directory to remove.
    """
    shutil.rmtree(staging, ignore_errors=True)
    if staging.exists():
        logger.error(
            "Could not remove the staging directory %s after a failed build. It holds a "
            "partial package and nothing else will clean it up — remove it by hand.",
            staging,
        )
