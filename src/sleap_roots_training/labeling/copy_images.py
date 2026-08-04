"""Gather each selected frame's image under its curated name.

Ported from the vault workflow's ``copy_selected_images.py`` (talmolab/sleap-roots-training#26;
Box copy 2026-08-03). This is the bridge between the two names a manifest row carries:
:mod:`~sleap_roots_training.labeling.select_samples` writes ``source_image`` — the real path
inside the downloaded scan — and ``output_filename`` — the curated name the builder reads out
of ``images/``. Nothing else connects them.

This module is the faithful port; its behavior is the vault script's, including the parts
design.md records as defective. Deviations land in their own commit, per Decision 1.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def copy_selected_images(
    manifest_csv: Path,
    experiment_dir: Path,
    output_dir: Path,
) -> tuple[int, int]:
    """Copy every manifest row's source image into the curated images directory.

    Warns and continues past a source that does not resolve, and returns normally
    however many rows were missed (design.md F5). Combined with the builder's own
    warn-and-continue, a run whose sources are entirely unreachable reports success
    twice and produces an empty package. Task 3.4 replaces this; it is preserved here
    so the characterization tests have the original behavior to pin.

    Args:
        manifest_csv: Path to ``sample_manifest.csv``.
        experiment_dir: Root of the experiment folder, which the vault script documents
            as the directory containing ``images_downloader_output/``. design.md F8
            records that Bloom's own ``scan_path`` is relative to the *download* dir
            instead, so this base misses every row by one segment for a ``bloomctl``
            export.
        output_dir: Destination ``images/`` directory.

    Returns:
        A ``(copied, missing)`` pair. ``copied`` counts copy *calls*, not resulting
        files, so duplicate ``output_filename`` values overwrite and still count twice.
    """
    manifest = pd.read_csv(manifest_csv)
    output_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = 0
    for _, row in manifest.iterrows():
        # `lstrip` is a character-set strip, not a prefix strip: it eats every leading
        # `.` and `/`, so an absolute `source_image` loses its root and resolves nowhere.
        # Task 0.9 established `bloomctl` never emits one, so this is a latent trap
        # rather than live breakage — 3.4 replaces it with an explicit rule.
        rel_path = row["source_image"].lstrip("./")
        src = experiment_dir / rel_path
        dst = output_dir / row["output_filename"]

        if not src.exists():
            logger.warning("Missing %s", src)
            missing += 1
            continue

        shutil.copy2(src, dst)
        copied += 1

    logger.info("Copied %d images to %s", copied, output_dir)
    if missing:
        logger.warning("%d images were missing!", missing)
    else:
        logger.info("All images copied successfully.")
    return copied, missing
