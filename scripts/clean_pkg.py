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

Usage (run on the GPU box, which has the ``[train]`` extra with ``sleap-io`` installed):
    uv run --no-sync python scripts/clean_pkg.py <in.pkg.slp> <out.pkg.slp>

Sanity check the printed summary: nodes should be ``r1..r6`` and images 1088x2048 grayscale.
"""

from __future__ import annotations

import sys

import sleap_io as sio


def clean(inp: str, out: str) -> None:
    """Strip ``source_video`` from every video in ``inp`` and re-embed to ``out``.

    Two things make these v000 ``.pkg.slp`` files fail on the GPU box:

    1. Each video keeps a ``source_video`` provenance pointer back to the SMB share; the box
       can't see the share, so resolving it raises ``PermissionError``. We null it.
    2. The files carry a stray video with **zero labeled frames** whose shape can't be resolved
       off the share. sleap-io's ``embed_all_videos`` path (the default in ``save_slp``) then
       calls ``_create_empty_embedded_video`` for it and crashes on ``video.shape is None``. Since
       a frame-less video is useless for training, we drop it (identity-based, to sidestep any
       ``Video`` hashability quirks) before re-embedding.
    """
    labels = sio.load_slp(
        inp, open_videos=False
    )  # don't touch the share-backed source video

    for video in labels.videos:
        video.source_video = None  # drop the dangling provenance pointer

    # Keep only videos that actually carry labeled frames (drops the frame-less stray).
    used_ids: set[int] = set()
    for lf in labels:
        used_ids.add(id(lf.video))
    keep = [v for v in labels.videos if id(v) in used_ids]
    dropped = len(labels.videos) - len(keep)
    if dropped:
        # Prune suggestions pointing at videos we're about to drop, then swap the video list.
        labels.suggestions = [
            sf for sf in getattr(labels, "suggestions", []) if id(sf.video) in used_ids
        ]
        labels.videos = keep

    # sleap-io signature is save_slp(labels, filename, ...): labels FIRST, path SECOND.
    sio.save_slp(
        labels, out, embed=True
    )  # self-contained: frames embedded, no external refs

    nodes = [n.name for n in labels.skeletons[0].nodes]
    shapes = [v.shape for v in labels.videos]
    print(
        f"{out}: {len(labels)} frames, {len(keep)} video(s) kept ({dropped} frame-less dropped), "
        f"nodes={nodes}, shapes={shapes}"
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
