"""Read per-file facts out of a labels file.

Everything here comes from the file. Nothing is inferred from a name and nothing is
fetched, so this module runs against a share with no credentials and no network.

Two ``sleap_io`` 0.7.1 details shape it. The instance counts are spelled
``Labels.n_user_instances`` and ``Labels.n_pred_instances`` — only
``user_instances``/``predicted_instances`` are absent at the ``Labels`` level. The
accessors that exist read the instance store directly **when the file is loaded
lazily**, which is why ``read_facts`` passes ``lazy=True``: measured against real files
that is 2.2x on a random sample and 7.6x (and -82 MB) on the worst case, with identical
results across 80 files. Without it both accessors fall back to summing over every
``LabeledFrame``, which is what an earlier version of this docstring wrongly claimed to
have avoided. And ``Labels.skeleton`` raises ``ValueError`` for *both*
zero skeletons and more than one, differing only in message, so the two states are
separated on ``len(Labels.skeletons)`` instead of on the exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sleap_io as sio

#: The file carries no skeleton at all.
NO_SKELETON = "no-skeleton"

#: The ordinary case: exactly one skeleton.
SINGLE_SKELETON = "single-skeleton"

#: Several skeletons in one file — a real state on the share, not a failure.
MULTIPLE_SKELETONS = "multiple-skeletons"

#: The file could not be read; see :attr:`FileFacts.error`.
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class FileFacts:
    """What one labels file says about itself.

    Attributes:
        path: The file these facts came from.
        skeleton_state: One of :data:`NO_SKELETON`, :data:`SINGLE_SKELETON`,
            :data:`MULTIPLE_SKELETONS` or :data:`UNREADABLE`.
        skeleton_names: Every skeleton name, in file order. A name may be the
            auto-generated ``Skeleton-N`` form, which carries no species.
        node_names: Node names of the first skeleton, which is the one instances are
            counted against. Empty when there is no skeleton.
        frame_count: Labeled frames, or ``None`` if the file could not be read.
        user_instances: User-labeled instances across all frames.
        predicted_instances: Model-predicted instances across all frames.
        video_filenames: Every path the file references for its images, unredacted.
            Redaction happens at emission; this is the raw recorded value.
        error: Why the file could not be read, or ``None``.
    """

    path: Path
    skeleton_state: str
    skeleton_names: tuple[str, ...] = ()
    node_names: tuple[str, ...] = ()
    frame_count: Optional[int] = None
    user_instances: Optional[int] = None
    predicted_instances: Optional[int] = None
    video_filenames: tuple[str, ...] = ()
    error: Optional[str] = None

    @property
    def node_count(self) -> Optional[int]:
        """Nodes on the first skeleton, or ``None`` when there is no skeleton to count.

        Zero is a real answer and must not read as "unknown": a skeleton carrying no
        nodes is a finding, and returning ``None`` made it falsy and dropped it from the
        gap analysis exactly like an unreadable file.
        """
        if self.skeleton_state in (NO_SKELETON, UNREADABLE):
            return None
        return len(self.node_names)


def _referenced_paths(labels: "sio.Labels") -> tuple[str, ...]:
    """Return every image path a labels file references, in file order.

    Prefers ``source_video`` where it exists. Under ``embed=True`` the video is an
    ``HDF5Video`` whose ``filename`` is just the ``.slp`` that was opened — re-derived at
    load time, not provenance — while ``source_video.filename`` holds the real recorded
    paths. Either may be a list rather than a string: a video built from image files
    carries one entry per frame.

    Args:
        labels: The loaded project.

    Returns:
        The referenced paths, de-duplicated, preserving first-seen order.
    """
    found: list[str] = []
    for video in labels.videos:
        source = getattr(video, "source_video", None)
        raw = getattr(source, "filename", None) if source is not None else None
        if raw is None:
            raw = getattr(video, "filename", None)
        if raw is None:
            continue
        for entry in raw if isinstance(raw, (list, tuple)) else [raw]:
            text = str(entry)
            if text not in found:
                found.append(text)
    return tuple(found)


def read_facts(path: Path) -> FileFacts:
    """Read one labels file, recording a failure rather than raising it.

    The catch is deliberately broad. A labels file whose video was built from a filename
    *list* raises ``TypeError`` from inside ``sleap_io`` on load — not the ``ValueError``
    or ``OSError`` a narrower handler would expect — and one bad file must not end a scan
    whose whole purpose is to establish what exists.

    Args:
        path: The labels file to read.

    Returns:
        Its facts, or a record carrying :data:`UNREADABLE` and the error text.
    """
    path = Path(path)
    try:
        # `open_videos=False`: nothing here needs pixels, and opening backends would
        # try to reach image paths recorded on other machines — slow at best, and a
        # failure that has nothing to do with the file being readable. It does not
        # avoid the list-filename `TypeError`; only the broad catch below does.
        labels = sio.load_slp(str(path), open_videos=False, lazy=True)
        skeletons = list(labels.skeletons)
        if not skeletons:
            state = NO_SKELETON
        elif len(skeletons) == 1:
            state = SINGLE_SKELETON
        else:
            state = MULTIPLE_SKELETONS

        return FileFacts(
            path=path,
            skeleton_state=state,
            skeleton_names=tuple(s.name for s in skeletons if s.name is not None),
            node_names=tuple(n.name for n in skeletons[0].nodes) if skeletons else (),
            frame_count=len(labels.labeled_frames),
            user_instances=labels.n_user_instances,
            predicted_instances=labels.n_pred_instances,
            video_filenames=_referenced_paths(labels),
        )
    except Exception as error:  # noqa: BLE001 - one bad file must not end the scan
        return FileFacts(path=path, skeleton_state=UNREADABLE, error=str(error))
