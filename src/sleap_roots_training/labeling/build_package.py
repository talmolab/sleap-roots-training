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

Two further deviations, each landed in its own commit. The ``.slp`` **embeds its images**
(section 5, Decision 2), so the package does not depend on paths that outlive it. And the
skeletons and output names come from the committed per-crop table rather than being
hardcoded to soybean and hand-edited per crop (section 6, Decision 7).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd
import sleap_io as sio

from sleap_roots_training.labeling.layout import project_filename
from sleap_roots_training.labeling.metadata import PackageMetadata
from sleap_roots_training.labeling.skeletons import lookup_skeleton

logger = logging.getLogger(__name__)


def rebuild_instance(
    pred_inst: sio.PredictedInstance, skeleton: sio.Skeleton
) -> sio.PredictedInstance:
    """Rebuild a predicted instance against a different (canonical) skeleton.

    Instances loaded from ``.slp`` files carry their own skeleton object. Aggregating many
    prediction files into one ``Labels`` would otherwise accumulate one duplicate skeleton
    per file; rebuilding against the canonical one leaves exactly one skeleton per root
    type in the saved project.

    This is also the one place the advisory skeleton table is checked against reality — the
    predictions were produced by a model with its own node count, and the table says what a
    labeler is supposed to place. It used to do that check *accidentally*, by letting numpy
    raise ``could not broadcast input array from shape (6,) into shape (4,)``, which names
    neither the species, the root type, the table row, nor which number came from where
    (blocking review of #40).

    Args:
        pred_inst: The predicted instance as loaded from a prediction file.
        skeleton: The canonical skeleton to rebuild against. Must have the same node
            names in the same order.

    Returns:
        An equivalent instance bound to ``skeleton``.

    Raises:
        ValueError: If the prediction's node count differs from the skeleton's, or if its
            node names are not the skeleton's in the same order.
    """
    # `pred_inst.points` is a structured array; these are field views, not a Python loop
    # over points (measured ~12x faster, identical output).
    xy = np.asarray(pred_inst.points["xy"], dtype=np.float64)
    scores = np.asarray(pred_inst.points["score"], dtype=np.float64)
    if len(xy) != len(skeleton.nodes):
        raise ValueError(
            f"a predicted instance has {len(xy)} node(s) but the {skeleton.name!r} "
            f"skeleton the package labels with has {len(skeleton.nodes)} "
            f"({', '.join(skeleton.node_names)}). The node count comes from the committed "
            "skeleton table (`labeling/data/skeletons.yaml`), which is transcribed and "
            "partly unverified; the predictions come from whichever model produced them. "
            "One of the two is wrong for this crop — confirm the count against Bloom or an "
            "existing label collection before building."
        )
    # The rebind is *positional* — point i of the prediction becomes node i of the
    # canonical skeleton — so agreeing on the count is not enough. Only the count was
    # checked, while this docstring promised "the same node names in the same order"
    # (blocking review of #40, second pass). A model emitting the chain tip-first, or under
    # any other permutation, would be rebound to `r1..rN` base-first without complaint:
    # every root angle and every base/tip anchoring in the resulting ground truth silently
    # reversed, and the labeler shown plausible points they would correct the positions of
    # rather than the order.
    predicted_names = tuple(pred_inst.skeleton.node_names)
    canonical_names = tuple(skeleton.node_names)
    if predicted_names != canonical_names:
        detail = (
            "the same nodes in a different order"
            if sorted(predicted_names) == sorted(canonical_names)
            else "different node names"
        )
        raise ValueError(
            f"a predicted instance carries {detail} than the {skeleton.name!r} skeleton "
            f"the package labels with: predictions have {list(predicted_names)}, the "
            f"package uses {list(canonical_names)}. Instances are rebound by position, so "
            "building past this would attach each prediction's coordinates to whichever "
            "node happens to share its index — reversing root polarity if the order is "
            "reversed. `r1` is the base and the last node is the tip; re-export the "
            "predictions under that convention, or correct the skeleton table."
        )
    return sio.PredictedInstance.from_numpy(
        points_data=xy,
        skeleton=skeleton,
        point_scores=scores,
        score=float(pred_inst.score),
    )


#: Environment variable overriding :data:`EMBED_PAYLOAD_CEILING_BYTES`.
EMBED_CEILING_ENV = "SLEAP_ROOTS_LABELING_EMBED_CEILING_BYTES"

#: Largest curated-image payload one ``.slp`` may embed, in bytes. Default 2 GiB.
#:
#: ``save_slp(embed=True)`` accumulates every encoded frame in memory before writing — see
#: sleap-io's ``process_and_embed_frames`` — at measured ~1:1 with the payload bytes. The
#: real shipped WEEP package is 185.6 MB and fine; the published collections reach 1.2 GB,
#: and Decision 6's re-derive-and-widen path multiplies that. A build that exceeds what the
#: machine can hold is killed with SIGKILL, which runs no ``except`` handler — so
#: :mod:`package`'s staging cleanup never gets to run and a full package's worth of bytes is
#: left behind. Failing *before* the allocation is the only place this can be caught, and 2
#: GiB keeps projected RSS inside a 4 GB pod with room for the interpreter.
EMBED_PAYLOAD_CEILING_BYTES = 2 * 1024**3


def _embed_payload_ceiling() -> int:
    """Return the configured embed payload ceiling in bytes.

    Returns:
        The override from :data:`EMBED_CEILING_ENV` if set and positive, else
        :data:`EMBED_PAYLOAD_CEILING_BYTES`. A non-numeric or non-positive override is
        ignored with a warning rather than failing the build over a setting.
    """
    raw = os.environ.get(EMBED_CEILING_ENV)
    if raw is None:
        return EMBED_PAYLOAD_CEILING_BYTES
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        logger.warning(
            "%s is %r, which is not a positive integer; using the default ceiling of "
            "%.1f GiB.",
            EMBED_CEILING_ENV,
            raw,
            EMBED_PAYLOAD_CEILING_BYTES / 1024**3,
        )
        return EMBED_PAYLOAD_CEILING_BYTES
    return value


def _assert_embeddable(
    images_dir: Path, manifest: pd.DataFrame, root_type: str
) -> None:
    """Fail before ``save_slp`` if this project's images will not fit in memory.

    Args:
        images_dir: The curated images directory.
        manifest: The loaded manifest, naming the images each project embeds.
        root_type: The root type about to be written, for the error message.

    Raises:
        ValueError: If the payload exceeds the configured ceiling.
    """
    ceiling = _embed_payload_ceiling()
    payload = 0
    for name in manifest["output_filename"]:
        path = images_dir / str(name)
        if path.is_file():
            payload += path.stat().st_size
    if payload <= ceiling:
        return
    raise ValueError(
        f"the {root_type!r} project would embed {payload / 1024**3:.2f} GiB of curated "
        f"images, above the {ceiling / 1024**3:.2f} GiB ceiling. Embedding holds every "
        "encoded frame in memory before writing, at roughly the payload size, so this "
        "build would likely be killed by the OS — and a SIGKILL runs no cleanup, leaving "
        "a partial package behind that nothing sweeps. Build the experiment as several "
        "narrower packages (fewer plants per group, or fewer views), or raise "
        f"{EMBED_CEILING_ENV} if this machine genuinely has the memory."
    )


def _is_entirely_unlocated(instance: sio.PredictedInstance) -> bool:
    """Return whether an instance has no located keypoint at all.

    Args:
        instance: The rebuilt instance.

    Returns:
        ``True`` if every node's coordinates are NaN, which is what SLEAP writes for a
        frame it tracked nothing in.
    """
    return bool(np.all(np.isnan(np.asarray(instance.points["xy"], dtype=np.float64))))


def prediction_file_for(
    scan_id: object, predictions_dir: Path, root_type: str
) -> Optional[Path]:
    """Return the prediction file a scan's root type is read from, if there is one.

    Stated once, because two callers depend on picking the *same* file: the builder, which
    reads the frames, and :func:`prediction_models`, which records what produced them. A
    provenance record naming a different file than the build used would be worse than none.

    Args:
        scan_id: The scan's Bloom id.
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory.
        root_type: The root type.

    Returns:
        The chosen path, or ``None`` if no file matches.
    """
    matches = sorted(
        predictions_dir.glob(f"scan_{scan_id}.model_*.root_{root_type}.slp")
    )
    if not matches:
        return None
    if len(matches) > 1:
        logger.warning(
            "Multiple %s predictions for scan %s, using first", root_type, scan_id
        )
    return matches[0]


def prediction_models(
    manifest: pd.DataFrame, predictions_dir: Path, root_types: Sequence[str]
) -> tuple[str, ...]:
    """Return the distinct model identifiers whose predictions seeded this package.

    New in the blocking review of #40. Labelers demonstrably anchor on the predictions —
    the README calls them starting points — so the model that produced them is a
    confounder in the resulting ground truth, and a package built from model A was
    indistinguishable from one built from model B. Nothing recorded it.

    Args:
        manifest: The loaded manifest.
        predictions_dir: The pipeline's ``sleap_roots_traits_input/`` directory.
        root_types: The root types the package declares.

    Returns:
        The distinct model identifiers, sorted. Empty if no prediction file was found.
    """
    found = set()
    for scan_id in manifest["scan_id"].unique():
        for root_type in root_types:
            path = prediction_file_for(scan_id, Path(predictions_dir), root_type)
            if path is None:
                continue
            # `scan_{id}.model_{name}.root_{type}.slp` — the pipeline's own naming.
            parts = path.name.split(".")
            if len(parts) >= 2 and parts[1].startswith("model_"):
                found.add(parts[1])
    return tuple(sorted(found))


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
    path = prediction_file_for(scan_id, predictions_dir, root_type)
    if path is None:
        return []
    labels = sio.load_slp(str(path), open_videos=False)
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


def skeleton_for(species: str, root_type: str, ages: Sequence[int]) -> sio.Skeleton:
    """Return the skeleton a package of this species, root type, and age span uses.

    Deviation (task 6.6). The vault script hardcoded a 6-node ``soybean_primary`` and a
    4-node ``soybean_lateral`` and was edited by hand per crop; this reads the committed
    table instead (design.md Decision 7). There was no parameterized original to port.

    A package spans several plant ages, and the table splits rice by age — young 2-5 DAG
    carries primary and crown, old 6-10 DAG carries crown only. A selection spanning that
    boundary therefore has no single answer, so it fails here rather than silently
    labeling half the package against the wrong skeleton.

    Args:
        species: Crop, already validated against ``SPECIES_VOCAB``.
        root_type: Root type, already validated against ``ROOT_TYPE_VOCAB``.
        ages: The distinct plant ages the manifest covers, in days.

    Returns:
        The skeleton to label with.

    Raises:
        ValueError: If the table has no row for the pair, if an age falls outside every
            window, or if the package's ages straddle an age split.
    """
    rows = {lookup_skeleton(species, root_type, int(age)) for age in ages}
    if len(rows) > 1:
        windows = sorted(str(row.age) for row in rows)
        raise ValueError(
            f"({species!r}, {root_type!r}) resolves to more than one skeleton across the "
            f"ages this package covers ({sorted(int(a) for a in ages)} DAG): the table "
            f"splits it at {windows}. Build one package per age window rather than one "
            "package labeled against two skeletons."
        )
    return rows.pop().to_skeleton()


#: Manifest columns the builder reads directly. Narrower than ``MANIFEST_COLUMNS`` —
#: validating the whole package contract is :mod:`validate`'s job — but wider than the copy
#: step's, which does not touch the age or the view.
REQUIRED_COLUMNS = (
    "scan_id",
    "plant_age_days",
    "view_index",
    "frame_index",
    "output_filename",
)


def _assert_buildable_manifest(manifest: pd.DataFrame, manifest_csv: Path) -> None:
    """Fail if the manifest cannot be built from, before any file is opened.

    Deviation (blocking review of #40). Neither condition was checked. A renamed column
    surfaced as a bare ``KeyError`` from wherever it was first indexed, which ``cli.py``'s
    ``except (OSError, ValueError)`` does not catch, so the operator got a traceback rather
    than the named error ``_labeling_error`` exists to produce. An empty manifest reached
    ``skeleton_for`` and died as ``KeyError: 'pop from an empty set'`` — raw, undocumented,
    and blaming the skeleton table for an empty selection three stages upstream.

    Args:
        manifest: The loaded manifest.
        manifest_csv: Its path, for the error message.

    Raises:
        ValueError: If a required column is absent, or the manifest has no rows.
    """
    absent = [column for column in REQUIRED_COLUMNS if column not in manifest.columns]
    if absent:
        raise ValueError(
            f"{manifest_csv.name} is missing required column(s): {', '.join(absent)}. "
            f"The builder reads {', '.join(REQUIRED_COLUMNS)}."
        )
    if manifest.empty:
        raise ValueError(
            f"{manifest_csv.name} has no rows, so there are no frames to build. An empty "
            "selection is not an empty result to pass along: every stage downstream "
            "accepts it and reports success, which is design.md F1. Re-run selection — a "
            "header-only manifest means its inputs did not overlap."
        )


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
    contributes no labels *for any declared root type* fails the build, and a requested
    root type with no frames fails the build. ``output_dir`` is created only once both
    projects are assembled, so a failed build leaves no directory a later stage could
    mistake for a complete package.

    A scan whose predictions do not cover every selected view fails too (deviation,
    blocking review of #40). That case used to warn and succeed, so the written ``.slp``
    was quietly shorter than the manifest — and since the frames a prediction file omits
    are the frames the model failed on, the package's ground truth was biased toward what
    the model already got right. Only a totally absent prediction file was fatal; a file
    covering the wrong frame range, which is what a re-spread view set or a partial
    pipeline run produces, was not.

    **A frame the model found nothing in is not that case, and ships empty** (second review
    pass). The first version of the fix could not tell the two apart: both produced no
    ``LabeledFrame``, so a young plant with genuinely no lateral roots failed the build
    just like predictions covering the wrong views. That left the operator only two ways
    out — re-run prediction, or drop the root type from the package — and the second
    reintroduces the same bias at package granularity. Writing an empty frame makes the
    absence *recordable*: the labeler opens it, confirms nothing is there, and the corpus
    gains a true negative it previously had no way to express. The build still fails if a
    declared root type is empty in every frame of every scan.

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
    _assert_buildable_manifest(manifest, Path(manifest_csv))
    logger.info("Loaded manifest with %d rows", len(manifest))

    # Skeletons first: they depend only on the manifest's age column and the committed
    # table, so a species the table does not cover fails before any image is judged.
    ages = sorted({int(age) for age in manifest["plant_age_days"]})
    skeletons = {
        rt: skeleton_for(metadata.species, rt, ages) for rt in metadata.root_types
    }
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
    # Scans that have predictions, but not for every root type this package declares.
    short: list[tuple[object, list[str]]] = []
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

        # Views this scan's predictions do not cover, per root type. That is a different
        # thing from a view the model covered and found nothing in, and the two used to be
        # indistinguishable downstream (blocking review of #40, second pass): both produced
        # no `LabeledFrame`, so genuine absence — a 3 DAG soybean with no laterals yet —
        # failed the build exactly like a prediction file covering the wrong frame range.
        # The only recourses the error offered were to re-run prediction or to drop the
        # root type, and dropping it reintroduces the very bias the check exists to stop,
        # at package granularity instead of frame granularity.
        uncovered: dict[str, list[int]] = {rt: [] for rt in metadata.root_types}
        for _, row in scan_rows.iterrows():
            target_idx = int(row["frame_index"])
            # Prediction files are 0-indexed over the full rotation; view_index is 1-based.
            pred_frame_idx = row["view_index"] - 1
            for root_type, pred_frames in predictions.items():
                pred_lf = next(
                    (lf for lf in pred_frames if lf.frame_idx == pred_frame_idx), None
                )
                if pred_lf is None:
                    uncovered[root_type].append(int(row["view_index"]))
                    continue
                # An instance whose every keypoint is NaN is not an observation, so it is
                # dropped. Partially-NaN instances are kept: an occluded or
                # early-terminating lateral root is real data, and its visible nodes are a
                # genuine starting point.
                instances = [
                    rebuilt
                    for rebuilt in (
                        rebuild_instance(inst, skeletons[root_type])
                        for inst in pred_lf.instances
                    )
                    if not _is_entirely_unlocated(rebuilt)
                ]
                # Written even when empty. The model looked at this frame and found
                # nothing, which is a *result* — the labeler opens it, confirms the
                # absence, and that confirmation is ground truth the corpus could not
                # previously record. `embed=True` embeds the pixels either way, so the
                # frame is openable.
                frames[root_type].append(
                    sio.LabeledFrame(
                        video=scan_video,
                        frame_idx=target_idx,
                        instances=instances,
                    )
                )

        covered = [rt for rt in metadata.root_types if not uncovered[rt]]
        for root_type in covered:
            videos[root_type].append(scan_video)
        missing_types = sorted(set(metadata.root_types) - set(covered))
        if missing_types:
            short.append((scan_id, missing_types))

    if unpredicted:
        raise ValueError(
            f"{len(unpredicted)} scan(s) in the manifest have no predictions for any "
            f"requested root type ({', '.join(metadata.root_types)}): {unpredicted}. "
            "A scan that contributes nothing is a selection the package cannot honor."
        )

    if short:
        listed = "\n  ".join(
            f"scan_id {scan_id}: {', '.join(types)}" for scan_id, types in short[:10]
        )
        more = f"\n  ... and {len(short) - 10} more" if len(short) > 10 else ""
        raise ValueError(
            f"{len(short)} scan(s) have predictions that do not cover every selected view, "
            f"for these root type(s):\n  {listed}{more}\nThis is not the same as a frame "
            "the model found nothing in — that is a result, and it ships as an empty frame "
            "for the labeler to confirm. This is a frame the model was never asked about, "
            "so skipping it would drop exactly the frames the model could not detect: the "
            "hardest and most informative examples, biasing the package toward what the "
            "model already gets right. Re-run prediction over the full rotation, or select "
            "the views the predictions do cover."
        )

    # Every declared root type must carry at least one *located* instance somewhere in the
    # package. A frame the model found nothing in is a legitimate contribution and ships
    # empty (above), but a root type that is empty in every frame of every scan is a
    # package promising labels it does not have — and a labeler would be handed a whole
    # project with nothing to correct. This is the check the earlier per-root-type "no
    # labeled frames" guard was reaching for; it became reachable again once empty frames
    # started being written.
    barren = [
        rt for rt in metadata.root_types if not any(lf.instances for lf in frames[rt])
    ]
    if barren:
        raise ValueError(
            f"root type(s) {barren} have no predicted instance in any frame of any scan, "
            "so every frame in those projects would be empty. An empty frame is a "
            "meaningful result where the model found nothing in *some* frames; a project "
            "that is empty throughout means the predictions for this root type are absent "
            "or the package should not declare it."
        )

    for root_type in metadata.root_types:
        blank = sum(1 for lf in frames[root_type] if not lf.instances)
        if blank:
            logger.info(
                "%s: %d of %d frame(s) carry no predicted instance — the model found "
                "nothing there. They ship for the labeler to confirm the absence, which "
                "is ground truth the corpus cannot otherwise record.",
                root_type,
                blank,
                len(frames[root_type]),
            )

    # Before `output_dir` is created and before any `save_slp`: the ceiling exists to
    # stop an allocation the machine cannot satisfy, so checking it after writing the
    # first project would defeat the point.
    for root_type in metadata.root_types:
        _assert_embeddable(images_dir, manifest, root_type)

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
        # Deviation (task 6.6): the vault script hardcoded `soybean_weep_*`. The naming rule
        # itself lives in `layout.project_filename`, which validation reads too — it used to
        # be re-typed here, so the one place the docstring claimed it was "stated once" was
        # the one place it was stated twice (blocking review of #40).
        path = output_dir / project_filename(metadata, root_type, version)
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
