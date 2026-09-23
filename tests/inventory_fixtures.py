"""Builders for the label-corpus trees the inventory tests scan.

Everything here writes into ``tmp_path``. Nothing is committed: ``.gitignore`` carries
``*.slp``, so a fixture checked into ``tests/fixtures/`` would pass locally and vanish in
CI, where the absent file surfaces as an unrelated read error.

Two builders, because the tests need two different things. Discovery only reads names off
the filesystem, so :func:`touch_labels` writes a placeholder and costs nothing. Reading
needs a real project, so :func:`write_labels` builds one with ``sleap_io``.

``write_labels`` takes image paths and calls ``Video.from_filename``. Do **not** reach for
``sio.Video(filename=[...], open_backend=False)`` instead: it constructs without
complaint and even saves, then raises ``TypeError: expected str, bytes or os.PathLike
object, not list`` on load — inside whatever module is reading, which makes it look like a
reader bug. ``open_videos=False`` does not avoid it. Note also that
``Video.from_filename(list).filename`` is itself a list, one entry per frame, so a reader
must not assume it is a string.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import sleap_io as sio

from conftest import write_jpeg

__all__ = [
    "touch_labels",
    "write_labels",
    "build_share_tree",
]


def touch_labels(path: Path) -> Path:
    """Create a placeholder ``.slp`` for tests that only enumerate filenames.

    Args:
        path: Where to create the file; parents are created.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def write_labels(
    path: Path,
    *,
    skeleton_names: Sequence[str] = ("soybean_primary",),
    node_names: Sequence[str] = ("r1", "r2"),
    n_frames: int = 1,
    n_user: int = 1,
    n_pred: int = 0,
    image_dir: Optional[Path] = None,
) -> Path:
    """Write a real ``.slp`` project with the requested shape.

    Args:
        path: Where to write the project; parents are created.
        skeleton_names: One name per skeleton. Empty writes a project with no skeleton,
            which is a real state on the share and a distinct failure from having several.
        node_names: Node names, shared by every skeleton.
        n_frames: Labeled frames to write.
        n_user: User instances per frame, on the first skeleton.
        n_pred: Predicted instances per frame, on the first skeleton.
        image_dir: Where the frame images go; defaults to a sibling directory.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    images = image_dir if image_dir is not None else path.parent / f"_{path.stem}_img"
    frame_paths = [
        str(write_jpeg(images / f"f{i}.jpg")) for i in range(max(n_frames, 1))
    ]
    video = sio.Video.from_filename(frame_paths)

    skeletons = []
    for name in skeleton_names:
        skeleton = sio.Skeleton(list(node_names))
        # Set explicitly: an unnamed Skeleton() has name None, not the auto-generated
        # "Skeleton-N" the SLEAP GUI writes, which is the form that defeats the existing
        # `skeleton.name.partition("_")` check.
        skeleton.name = name
        skeletons.append(skeleton)

    points = np.array([[float(i + 1), float(i + 2)] for i in range(len(node_names))])
    frames = []
    for idx in range(n_frames):
        instances: list[object] = []
        if skeletons:
            instances += [
                sio.Instance.from_numpy(points, skeleton=skeletons[0])
                for _ in range(n_user)
            ]
            instances += [
                sio.PredictedInstance.from_numpy(
                    points,
                    skeleton=skeletons[0],
                    point_scores=np.ones(len(node_names)),
                    score=0.9,
                )
                for _ in range(n_pred)
            ]
        frames.append(sio.LabeledFrame(video=video, frame_idx=idx, instances=instances))

    labels = sio.Labels(frames)
    labels.videos = [video]
    if skeletons:
        labels.skeletons = list(skeletons)
    sio.save_slp(labels, str(path), embed=True, verbose=False)
    return path


def build_share_tree(root: Path, *, real: Iterable[str] = ()) -> Path:
    """Build a tree carrying every enumeration shape the share actually contains.

    The layout mirrors the measured corpus rather than an idealized one: derived files
    both inside and outside the derived directories, one basename repeated across
    directories, a packaged twin, per-labeler suffixes, and an unversioned file that is
    real labeling rather than scratch.

    Args:
        root: Directory to build under; created if absent.
        real: Paths, relative to ``root``, to write as real projects instead of
            placeholders. Everything else is a placeholder.

    Returns:
        ``root``.
    """
    root.mkdir(parents=True, exist_ok=True)
    wanted = set(real)

    layout = [
        # Candidates.
        "SLEAP_soybean/primary_6nodes/labels.v001.slp",
        "SLEAP_soybean/primary_6nodes/labels.v002.slp",
        "SLEAP_soybean/primary_6nodes/labels.v002.pkg.slp",
        "SLEAP_soybean/primary_6nodes/labels.v001_ana.slp",
        "SLEAP_soybean/primary_6nodes/labels.v001_ben.slp",
        # Same basename, different directory — must not supersede the above.
        "SLEAP_rice/primary_6nodes/labels.v001.slp",
        "SLEAP_wheat/seminal/labels_sr_5-14DAG.v004.slp",
        # The `.<text>.vNNN.slp` shape.
        "SLEAP_canola/primary/labels.combined.v003.slp",
        # Unversioned, and the newest real labeling on the share.
        "SLEAP_medicago_plates/combined_roots/MK24_roots.slp",
        # Derived by filename shape, sitting outside every derived directory.
        "SLEAP_soybean/primary_6nodes/labels.v002.predictions.slp",
        "SLEAP_rice/primary_6nodes/scan_001.predictions.slp",
        # Derived by location.
        "SLEAP_soybean/models/240101_unet/labels.v001.slp",
        "SLEAP_soybean/predictions/labels.v001.slp",
        "SLEAP_rice/train_test_split_0.8/train.slp",
    ]

    for relative in layout:
        target = root / relative
        if relative in wanted:
            write_labels(target)
        else:
            touch_labels(target)
    return root
