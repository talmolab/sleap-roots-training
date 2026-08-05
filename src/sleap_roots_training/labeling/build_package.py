"""Assemble the SLEAP labeling project files a labeler opens.

Ported from the vault workflow's ``build_slp_project.py`` (talmolab/sleap-roots-training#26;
Box copy 2026-07-29). Reads ``sample_manifest.csv`` and the curated ``images/`` directory the
copy step produced, pulls each frame's model predictions out of the pipeline's per-scan
prediction files, and writes one ``.slp`` per root type with those predictions as starting
points.

One ``Video`` per scan, matching sleap-roots' "one video per cylinder scan" convention; each
scan's video holds only the selected rotational views, in manifest ``frame_index`` order.

The build is **all-or-nothing** (tasks 4.4–4.7): metadata, curated images, and predictions
are all checked before ``output_dir`` is created, so a failed build leaves nothing behind
and an empty selection is never reported as a success. The vault script warned past each of
those and wrote both files anyway (design.md F1); its faithful behavior is in this file's
first commit.

It still saves with ``embed=False`` — the change that stops a package depending on paths
that outlive it is section 5, as its own commit (design.md Decision 2). The skeletons are
still the hardcoded soybean pair and the output names still say ``soybean_weep``; section 6
parameterizes both off a committed table (Decision 7).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import sleap_io as sio

from sleap_roots_training.labeling.metadata import PackageMetadata

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


def skeleton_for(species: str, root_type: str) -> sio.Skeleton:
    """Return the skeleton a package of this species and root type is labeled with.

    Still the vault script's hardcoded soybean pair. Section 6 replaces this with a
    committed, provenance-stamped table keyed by ``(species, root_type)`` (Decision 7);
    until then any other combination raises rather than silently receiving soybean's node
    counts, which would produce a package that looks fine and cannot be combined with
    anything.

    Args:
        species: Crop, already validated against ``SPECIES_VOCAB``.
        root_type: Root type, already validated against ``ROOT_TYPE_VOCAB``.

    Returns:
        The skeleton to label with.

    Raises:
        NotImplementedError: For any pair the hardcoded skeletons do not describe.
    """
    builders = {
        ("soybean", "primary"): make_primary_skeleton,
        ("soybean", "lateral"): make_lateral_skeleton,
    }
    try:
        return builders[(species, root_type)]()
    except KeyError:
        raise NotImplementedError(
            f"No skeleton is defined for ({species!r}, {root_type!r}). The builder still "
            "carries the vault script's hardcoded soybean primary/lateral pair; the "
            "committed per-crop skeleton table (design.md Decision 7) is what adds the "
            "rest."
        ) from None


def _resolve_scan_images(
    scan_rows: pd.DataFrame, images_dir: Path
) -> tuple[list[str], list[str]]:
    """Return one scan's curated image paths in frame order, and any that are absent."""
    paths = [
        str(images_dir / row["output_filename"]) for _, row in scan_rows.iterrows()
    ]
    return paths, [p for p in paths if not Path(p).exists()]


def build_slp_project(
    manifest_csv: Path,
    images_dir: Path,
    predictions_dir: Path,
    output_dir: Path,
    metadata: PackageMetadata,
    version: str = "v000",
) -> dict[str, Path]:
    """Build one ``.slp`` project per requested root type, or fail without writing.

    Deviation (tasks 4.4–4.7). The vault script warned past a scan whose curated images
    were missing, warned past a scan with no predictions, and then wrote both ``.slp``
    files and returned normally — so an unpopulated ``images_dir`` produced an empty
    labeling package that reported success (design.md F1). Everything is now validated
    before anything is written: a missing curated image fails the build, a scan that
    contributes no labels at all fails the build, and a requested root type with no
    frames fails the build. ``output_dir`` is created only once both projects are
    assembled, so a failed build leaves no directory a later stage could mistake for a
    complete package.

    Args:
        manifest_csv: Path to ``sample_manifest.csv``.
        images_dir: The curated ``images/`` directory the copy step populated.
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory, holding
            one prediction file per scan and root type.
        output_dir: Directory to write the ``.slp`` files into.
        metadata: The package's identity. Validated on construction, so a build cannot
            proceed with a missing or out-of-vocabulary field (task 4.6).
        version: Version string embedded in the output filenames.

    Returns:
        The path written for each root type, keyed by root type.

    Raises:
        FileNotFoundError: If any curated image named by the manifest is absent.
        ValueError: If ``frame_index`` is not a contiguous rank within a scan, if a scan
            has no predictions for any requested root type, or if a requested root type
            ends up with no labeled frames.
        NotImplementedError: If no skeleton is defined for the metadata's species and a
            requested root type.
    """
    manifest = pd.read_csv(manifest_csv)
    logger.info("Loaded manifest with %d rows", len(manifest))

    # Metadata and skeletons first: they depend on no input file, so a wrong species or
    # an unknown root type fails before anything on disk is read or judged.
    skeletons = {rt: skeleton_for(metadata.species, rt) for rt in metadata.root_types}
    frames: dict[str, list[sio.LabeledFrame]] = {rt: [] for rt in metadata.root_types}
    videos: dict[str, list[sio.Video]] = {rt: [] for rt in metadata.root_types}

    scan_groups = [
        (scan_id, _scan_frame_order(rows, scan_id))
        for scan_id, rows in manifest.groupby("scan_id")
    ]

    # Every curated image, across every scan, before a single video is opened — so the
    # report is "these N images are missing", not the first scan that happened to fail.
    absent: list[str] = []
    for _, scan_rows in scan_groups:
        absent.extend(_resolve_scan_images(scan_rows, images_dir)[1])
    if absent:
        listed = "\n  ".join(absent[:10])
        more = f"\n  ... and {len(absent) - 10} more" if len(absent) > 10 else ""
        raise FileNotFoundError(
            f"{len(absent)} of {len(manifest)} curated image(s) named by the manifest "
            f"are missing from {images_dir}:\n  {listed}{more}\nRun the copy step first; "
            "an empty or partial images directory is not a buildable package."
        )

    unpredicted: list[object] = []
    for scan_id, scan_rows in scan_groups:
        scan_image_paths, _ = _resolve_scan_images(scan_rows, images_dir)
        # One Video per scan, matching sleap-roots' "1 video per scan" convention.
        scan_video = sio.Video.from_filename(scan_image_paths)

        predictions = {
            rt: load_predictions_for_scan(scan_id, predictions_dir, rt)
            for rt in metadata.root_types
        }
        if not any(predictions.values()):
            unpredicted.append(scan_id)
            continue

        contributed: set[str] = set()
        for _, row in scan_rows.iterrows():
            target_idx = int(row["frame_index"])
            # Prediction files are 0-indexed over the full rotation; view_index is 1-based.
            pred_frame_idx = row["view_index"] - 1
            for root_type, pred_frames in predictions.items():
                for pred_lf in pred_frames:
                    if pred_lf.frame_idx != pred_frame_idx:
                        continue
                    instances = [
                        rebuild_instance(inst, skeletons[root_type])
                        for inst in pred_lf.instances
                    ]
                    if instances:
                        frames[root_type].append(
                            sio.LabeledFrame(
                                video=scan_video,
                                frame_idx=target_idx,
                                instances=instances,
                            )
                        )
                        contributed.add(root_type)
                    break

        for root_type in contributed:
            videos[root_type].append(scan_video)
        missing_types = sorted(set(metadata.root_types) - contributed)
        if missing_types:
            logger.warning(
                "Scan %s contributes no %s labels", scan_id, ", ".join(missing_types)
            )

    if unpredicted:
        raise ValueError(
            f"{len(unpredicted)} scan(s) in the manifest have no predictions for any "
            f"requested root type ({', '.join(metadata.root_types)}): {unpredicted}. "
            "A scan that contributes nothing is a selection the package cannot honor."
        )

    empty = [rt for rt in metadata.root_types if not frames[rt]]
    if empty:
        raise ValueError(
            f"No labeled frames were produced for root type(s) {empty}, so the build "
            "would write empty label files. Either the predictions do not cover the "
            "selected views, or the package should not declare these root types."
        )

    projects = {}
    for root_type in metadata.root_types:
        labels = sio.Labels(
            labeled_frames=frames[root_type],
            videos=videos[root_type],
            skeletons=[skeletons[root_type]],
        )
        labels.update()
        projects[root_type] = labels
        logger.info(
            "%s: %d frames across %d scan videos",
            root_type,
            len(frames[root_type]),
            len(videos[root_type]),
        )

    # Nothing on disk until every project is assembled.
    output_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for root_type, labels in projects.items():
        path = output_dir / f"soybean_weep_{root_type}_labels.{version}.slp"
        # Deviation (task 5.2), and the change issue #26 exists for. The vault script
        # saved `embed=False`, and six of the eight collections in
        # `wandb-registry-sleap-roots-labels` carry `repaired_from: "v0"` /
        # `embedded-images-repair` as a result: the external reference broke and the file
        # was hand-patched into a package afterwards. That repair is one-way —
        # `save_slp` restores the original video only "if available", so a package
        # repaired after its sources went unreachable is capped at whatever frames were
        # embedded at repair time, permanently. Embedding here means no
        # external-reference `.slp` is ever produced to be repaired later.
        sio.save_slp(labels, str(path), embed=True, verbose=False)
        logger.info("Saved %s labels: %s", root_type, path)
        written[root_type] = path
    return written
