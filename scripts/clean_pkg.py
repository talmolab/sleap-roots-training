"""Make a ``.pkg.slp`` self-contained by dropping its ``source_video`` provenance pointer.

The v000 held-out split files
(``.../20250625_cyl_arabidopsis_primary_receptive_field/train_test_split.v000/``) embed their
frames but keep a ``source_video`` pointer back to the original SMB share. On the GPU box the SSH
session cannot see that share, so any code that resolves the pointer raises ``PermissionError`` --
even though every frame is already embedded in the file. This script rewrites each video to drop
the dangling pointer and re-embeds the frames, producing a file that loads with the share
unmounted (which proves it is self-contained).

Loading with ``open_videos=False`` means the share-backed source video is never opened, so this
runs anywhere the file is reachable -- including the GPU box, which never sees the share.

``sleap_io`` is imported lazily (train-extra-only), so this module stays importable in the base
env for unit tests of the pure selection/guard logic.

Usage (run on the GPU box, which has the ``[train]`` extra with ``sleap-io`` installed):
    uv run --no-sync python scripts/clean_pkg.py <in.pkg.slp> <out.pkg.slp>

Sanity check the printed summary: nodes should be ``r1..r6`` and images 1088x2048 grayscale.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sleap_io import Video

#: SMB-share markers a cleaned file's ``source_video`` must never still point at.
_SHARE_MARKERS = ("multilab-na", "hpi_dev")


def _sha256(path: str) -> str:
    """Streamed sha256 of a file, so a cleaned dataset carries a content fingerprint now."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _select_videos(labels: object) -> tuple[list[Video], set[int]]:
    """Return ``(keep, used_ids)``: videos referenced by >=1 labeled frame, matched by identity.

    We key on ``id()`` rather than putting ``Video`` objects in a set. sleap-io's ``Video`` is
    ``@attrs.define(eq=False)`` (pinned v0.7.1), so it keeps identity-based equality and would in
    fact be hashable by identity; keying on ``id()`` makes that identity match explicit. After
    ``load_slp`` every ``LabeledFrame.video`` is the same object instance as an entry in
    ``labels.videos``, so the match is exact, not merely empirical.
    """
    used_ids: set[int] = set()
    for lf in labels:
        used_ids.add(id(lf.video))
    keep = [v for v in labels.videos if id(v) in used_ids]
    return keep, used_ids


def clean(inp: str, out: str) -> None:
    """Strip ``source_video`` from every video in ``inp`` and re-embed to ``out``.

    Two things make these v000 ``.pkg.slp`` files fail on the GPU box:

    1. Each video keeps a ``source_video`` provenance pointer back to the SMB share; the box
       can't see the share, so resolving it raises ``PermissionError``. We null it.
    2. The files carry a stray video with **zero labeled frames** whose shape can't be resolved
       off the share. sleap-io's ``embed_all_videos`` path (the default in ``save_slp``) then
       calls ``_create_empty_embedded_video`` for it and crashes on ``video.shape is None``. Since
       a frame-less video is useless for training, we drop it before re-embedding.

    Refuses to overwrite the input in place, guards the labeled-frame invariant explicitly (not via
    ``assert``, which ``python -O`` strips), and re-loads the output to confirm no share-backed
    ``source_video`` survived.
    """
    if Path(inp).resolve() == Path(out).resolve():
        raise SystemExit(
            f"refusing to overwrite the input in place: inp == out ({inp})"
        )

    import sleap_io as sio  # lazy: train-extra-only; keeps this module importable in the base env

    labels = sio.load_slp(
        inp, open_videos=False
    )  # don't touch the share-backed source video

    for video in labels.videos:
        video.source_video = None  # drop the dangling provenance pointer

    n_frames_before = len(labels)
    keep, used_ids = _select_videos(labels)
    dropped = len(labels.videos) - len(keep)

    # Refuse to write an empty package: a file with no labeled frames is not a valid training
    # input, and a silent 0-frame .pkg.slp would defeat the point of this script.
    if not keep:
        raise SystemExit(
            f"{inp}: no videos carry labeled frames; refusing to write empty {out}"
        )

    if dropped:
        # Prune suggestions pointing at videos we're about to drop, then swap the video list.
        labels.suggestions = [
            sf for sf in getattr(labels, "suggestions", []) if id(sf.video) in used_ids
        ]
        labels.videos = keep

    # Dropping frame-less videos must not change the labeled-frame set nor orphan any frame.
    # Explicit checks (a bare `assert` would be stripped under `python -O`).
    if len(labels) != n_frames_before:
        raise ValueError("labeled-frame count changed while dropping videos")
    kept_ids = {id(v) for v in labels.videos}
    if any(id(lf.video) not in kept_ids for lf in labels):
        raise ValueError("a labeled frame references a dropped video")

    if not labels.skeletons:
        raise ValueError(f"{inp}: file has no skeleton")
    nodes = [n.name for n in labels.skeletons[0].nodes]
    sio.save_slp(
        labels, out, embed=True
    )  # self-contained: frames embedded, no external refs

    # Verify the cleaned file is really self-contained: re-load it (the box never sees the share)
    # and confirm no surviving `source_video` still points at the SMB share.
    reloaded = sio.load_slp(out, open_videos=False)
    for v in reloaded.videos:
        fn = str(getattr(v.source_video, "filename", "") or "")
        if any(marker in fn for marker in _SHARE_MARKERS):
            raise ValueError(f"{out} still points at the share via source_video: {fn}")

    shapes = [v.shape for v in labels.videos]
    sha_in, sha_out = _sha256(inp), _sha256(out)
    # Persist the fingerprints next to the cleaned file so they outlive the console session.
    sidecar = Path(str(out) + ".sha256")
    sidecar.write_text(
        f"{sha_out}  {Path(out).name}\n{sha_in}  {Path(inp).name}\n", encoding="utf-8"
    )
    print(
        f"{out}: {len(labels)} frames, {len(keep)} video(s) kept ({dropped} frame-less dropped), "
        f"nodes={nodes}, shapes={shapes}\n"
        f"  sha256(in={Path(inp).name})={sha_in}\n"
        f"  sha256(out={Path(out).name})={sha_out}\n"
        f"  wrote {sidecar.name}"
    )


def main(argv: list[str]) -> int:
    """CLI entry point: clean the input ``.pkg.slp`` (argv[1]) into the output path (argv[2])."""
    if len(argv) != 3:
        print(
            "usage: python scripts/clean_pkg.py <in.pkg.slp> <out.pkg.slp>",
            file=sys.stderr,
        )
        return 2
    clean(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
