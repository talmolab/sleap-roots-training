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

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Mapping

import pandas as pd

from sleap_roots_training.labeling.build_package import build_slp_project, skeleton_for
from sleap_roots_training.labeling.copy_images import copy_selected_images
from sleap_roots_training.labeling.metadata import (
    PackageMetadata,
    PackageRecord,
    SelectionParameters,
    write_package_metadata,
)
from sleap_roots_training.labeling.render_readme import render_readme
from sleap_roots_training.labeling.validate import (
    IMAGES_DIRNAME,
    MANIFEST_FILENAME,
    validate_package,
)

logger = logging.getLogger(__name__)


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

    Args:
        manifest: The loaded manifest.
        selection: The parameters being recorded.

    Raises:
        ValueError: If any plant carries more views than ``views_per_plant`` allows.
    """
    per_plant = manifest.groupby("plant_qr_code").size()
    most = int(per_plant.max())
    if most > selection.views_per_plant:
        crowded = sorted(per_plant[per_plant > selection.views_per_plant].index)
        raise ValueError(
            f"selection parameter 'views_per_plant' is {selection.views_per_plant}, but "
            f"{MANIFEST_FILENAME} gives up to {most} views to a single plant "
            f"({crowded[:5]}). These parameters did not produce this manifest, so "
            "recording them would make the package's own re-derivation instructions wrong."
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
    staging = Path(
        tempfile.mkdtemp(dir=output_dir.parent, prefix=f".{output_dir.name}.partial-")
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
            ),
            staging,
        )
        render_readme(staging)
        validate_package(staging)
    except BaseException:
        # Including KeyboardInterrupt: a package half-written by an interrupted run is
        # the same artifact as one half-written by a crash.
        shutil.rmtree(staging, ignore_errors=True)
        raise

    staging.rename(output_dir)
    logger.info("Built labeling package: %s", output_dir)
    return output_dir
