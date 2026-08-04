"""Assemble the SLEAP labeling project files a labeler opens.

Ported from the vault workflow's ``build_slp_project.py`` (talmolab/sleap-roots-training#26;
Box copy 2026-07-29). Reads ``sample_manifest.csv`` and the curated ``images/`` directory the
copy step produced, pulls each frame's model predictions out of the pipeline's per-scan
prediction files, and writes one ``.slp`` per root type with those predictions as starting
points.

One ``Video`` per scan, matching sleap-roots' "one video per cylinder scan" convention; each
scan's video holds only the selected rotational views, in manifest ``frame_index`` order.

This is the faithful port, so it still saves with ``embed=False`` — the change that stops a
package depending on paths that outlive it is section 5, as its own commit (design.md
Decision 2). The skeletons are still the hardcoded soybean pair and the output names still
say ``soybean_weep``; section 6 parameterizes both off a committed table (Decision 7).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import sleap_io as sio

logger = logging.getLogger(__name__)


def rebuild_instance(
    pred_inst: sio.PredictedInstance, skeleton: sio.Skeleton
) -> sio.PredictedInstance:
    """Rebuild a predicted instance against a different (canonical) skeleton.

    Instances loaded from ``.slp`` files carry their own skeleton object. Aggregating many
    prediction files into one ``Labels`` would otherwise accumulate one duplicate skeleton
    per file; rebuilding against the canonical one leaves exactly one skeleton per root
    type in the saved project.

    Args:
        pred_inst: The predicted instance as loaded from a prediction file.
        skeleton: The canonical skeleton to rebuild against. Must have the same node
            names in the same order.

    Returns:
        An equivalent instance bound to ``skeleton``.
    """
    xy = np.array([pt["xy"] for pt in pred_inst.points], dtype=np.float64)
    scores = np.array([pt["score"] for pt in pred_inst.points], dtype=np.float64)
    return sio.PredictedInstance.from_numpy(
        points_data=xy,
        skeleton=skeleton,
        point_scores=scores,
        score=float(pred_inst.score),
    )


def make_primary_skeleton() -> sio.Skeleton:
    """Return the soybean primary-root skeleton: 6 nodes, ``r1`` (base) to ``r6`` (tip)."""
    return sio.Skeleton(
        nodes=["r1", "r2", "r3", "r4", "r5", "r6"],
        edges=[("r1", "r2"), ("r2", "r3"), ("r3", "r4"), ("r4", "r5"), ("r5", "r6")],
        name="soybean_primary",
    )


def make_lateral_skeleton() -> sio.Skeleton:
    """Return the soybean lateral-root skeleton: 4 nodes, ``r1`` (base) to ``r4`` (tip)."""
    return sio.Skeleton(
        nodes=["r1", "r2", "r3", "r4"],
        edges=[("r1", "r2"), ("r2", "r3"), ("r3", "r4")],
        name="soybean_lateral",
    )


def load_predictions_for_scan(
    scan_id: int, predictions_dir: Path, root_type: str
) -> list[sio.LabeledFrame]:
    """Load one scan's prediction frames for a root type.

    Args:
        scan_id: The scan's Bloom id.
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory.
        root_type: ``"primary"`` or ``"lateral"``.

    Returns:
        The prediction file's labeled frames, or an empty list if no file matches.
    """
    pattern = f"scan_{scan_id}.model_*.root_{root_type}.slp"
    matches = sorted(predictions_dir.glob(pattern))
    if not matches:
        return []
    if len(matches) > 1:
        logger.warning(
            "Multiple %s predictions for scan %s, using first", root_type, scan_id
        )
    labels = sio.load_slp(str(matches[0]), open_videos=False)
    return labels.labeled_frames


def _scan_frame_order(scan_rows: pd.DataFrame, scan_id: object) -> pd.DataFrame:
    """Return one scan's rows ordered by their authoritative within-scan position.

    Obligation from task 2.10. The vault script derived each frame's position by sorting
    on ``view_index`` and enumerating, and never read the manifest's ``frame_index``
    column — while ``output_filename`` embedded ``frame_index`` from the selection
    counter. Two independent derivations of one number, agreeing only because
    ``selected_views`` happens to be ascending. 2.10 pinned ``frame_index`` as the
    authoritative one and proved the derivations currently agree, so reading it here is a
    swap with no behavior change; leaving it would keep both derivations alive.

    Args:
        scan_rows: The manifest rows for one scan.
        scan_id: The scan's id, for the error message.

    Returns:
        The rows ordered by ``frame_index``, reindexed from zero.

    Raises:
        ValueError: If ``frame_index`` is not exactly ``0..n-1`` for this scan, since a
            frame's position has to index into its scan's video.
    """
    ordered = scan_rows.sort_values("frame_index").reset_index(drop=True)
    expected = list(range(len(ordered)))
    if list(ordered["frame_index"]) != expected:
        raise ValueError(
            f"scan_id {scan_id} has frame_index values "
            f"{list(ordered['frame_index'])}, expected {expected}. frame_index is a "
            "frame's position within its scan's video, so it must be a contiguous rank "
            "from zero."
        )
    return ordered


def build_slp_project(
    manifest_csv: Path,
    images_dir: Path,
    predictions_dir: Path,
    output_dir: Path,
    version: str = "v000",
) -> None:
    """Build the primary and lateral ``.slp`` project files.

    Warns and skips past a scan whose curated images are missing, then writes both
    ``.slp`` files and returns normally (design.md F1). Run against an unpopulated
    ``images_dir``, it reports success and produces empty label files — the second link
    in the silent-empty chain whose first link the copy step used to hold. Task 4.4
    changes this; it is preserved here so the characterization tests have the original
    behavior to pin.

    Args:
        manifest_csv: Path to ``sample_manifest.csv``.
        images_dir: The curated ``images/`` directory the copy step populated.
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory, holding
            one prediction file per scan and root type.
        output_dir: Directory to write the ``.slp`` files into.
        version: Version string embedded in the output filenames.
    """
    manifest = pd.read_csv(manifest_csv)
    logger.info("Loaded manifest with %d rows", len(manifest))

    primary_skeleton = make_primary_skeleton()
    lateral_skeleton = make_lateral_skeleton()

    primary_frames: list[sio.LabeledFrame] = []
    lateral_frames: list[sio.LabeledFrame] = []
    primary_videos: list[sio.Video] = []
    lateral_videos: list[sio.Video] = []
    scans_processed = 0
    scans_missing_pred = 0

    for scan_id, scan_rows in manifest.groupby("scan_id"):
        scans_processed += 1
        scan_rows = _scan_frame_order(scan_rows, scan_id)

        scan_image_paths = [
            str(images_dir / row["output_filename"]) for _, row in scan_rows.iterrows()
        ]
        missing = [p for p in scan_image_paths if not Path(p).exists()]
        if missing:
            logger.warning("Missing images for scan %s: %s", scan_id, missing)
            continue

        # One Video per scan, matching sleap-roots' "1 video per scan" convention.
        scan_video = sio.Video.from_filename(scan_image_paths)

        primary_pred_frames = load_predictions_for_scan(
            scan_id, predictions_dir, "primary"
        )
        lateral_pred_frames = load_predictions_for_scan(
            scan_id, predictions_dir, "lateral"
        )
        if not primary_pred_frames and not lateral_pred_frames:
            scans_missing_pred += 1
            continue

        scan_has_primary = False
        scan_has_lateral = False

        for _, row in scan_rows.iterrows():
            target_idx = int(row["frame_index"])
            # Prediction files are 0-indexed over the full rotation; view_index is 1-based.
            pred_frame_idx = row["view_index"] - 1

            for pred_lf in primary_pred_frames:
                if pred_lf.frame_idx == pred_frame_idx:
                    instances = [
                        rebuild_instance(inst, primary_skeleton)
                        for inst in pred_lf.instances
                    ]
                    if instances:
                        primary_frames.append(
                            sio.LabeledFrame(
                                video=scan_video,
                                frame_idx=target_idx,
                                instances=instances,
                            )
                        )
                        scan_has_primary = True
                    break

            for pred_lf in lateral_pred_frames:
                if pred_lf.frame_idx == pred_frame_idx:
                    instances = [
                        rebuild_instance(inst, lateral_skeleton)
                        for inst in pred_lf.instances
                    ]
                    if instances:
                        lateral_frames.append(
                            sio.LabeledFrame(
                                video=scan_video,
                                frame_idx=target_idx,
                                instances=instances,
                            )
                        )
                        scan_has_lateral = True
                    break

        if scan_has_primary:
            primary_videos.append(scan_video)
        if scan_has_lateral:
            lateral_videos.append(scan_video)

    logger.info(
        "Processed %d scans (%d missing predictions)",
        scans_processed,
        scans_missing_pred,
    )
    logger.info(
        "Primary: %d frames across %d scan videos",
        len(primary_frames),
        len(primary_videos),
    )
    logger.info(
        "Lateral: %d frames across %d scan videos",
        len(lateral_frames),
        len(lateral_videos),
    )

    for root_type, frames, videos, skeleton in (
        ("primary", primary_frames, primary_videos, primary_skeleton),
        ("lateral", lateral_frames, lateral_videos, lateral_skeleton),
    ):
        labels = sio.Labels(labeled_frames=frames, videos=videos, skeletons=[skeleton])
        labels.update()
        path = output_dir / f"soybean_weep_{root_type}_labels.{version}.slp"
        sio.save_slp(labels, str(path), embed=False)
        logger.info("Saved %s labels: %s", root_type, path)
