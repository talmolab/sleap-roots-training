"""Checks a labeling package must pass before it is published.

design.md Decision 2 splits the embed guarantee in two: the builder *performs* embedding, so
the on-disk package is already a complete artifact, and this module *verifies* it — which is
what makes the guarantee a property of the package rather than of the code path that
happened to write it. A package built by an older tool, or assembled by hand, is checked by
the same rule.

``#10``'s ``publish-labels`` calls this before any network call. Task 8.1 adds the layout,
manifest-column, and frame-count checks alongside the self-containment one landing here.
"""

from __future__ import annotations

from pathlib import Path

import sleap_io as sio


def _external_references(slp_path: Path) -> list[str]:
    """Return the external video paths a ``.slp`` depends on.

    A video whose frames are embedded records the ``.slp`` itself as its filename; the
    original paths survive only as ``source_video`` provenance, which nothing needs to
    open. Anything else is a path the package cannot guarantee.

    Args:
        slp_path: Path to the ``.slp`` file.

    Returns:
        The external paths referenced, empty if the file is self-contained.
    """
    # `open_videos=False` so an already-broken package is diagnosable rather than raising
    # on the very dependency being checked.
    labels = sio.load_slp(str(slp_path), open_videos=False)
    external: list[str] = []
    for video in labels.videos:
        filenames = (
            video.filename if isinstance(video.filename, list) else [video.filename]
        )
        if any(Path(name) != Path(slp_path) for name in filenames):
            external.extend(str(name) for name in filenames)
    return external


def slp_is_self_contained(slp_path: Path) -> bool:
    """Return whether a ``.slp`` carries its own images.

    Args:
        slp_path: Path to the ``.slp`` file.

    Returns:
        ``True`` if no video references a path outside the file itself.
    """
    return not _external_references(slp_path)


def assert_slp_is_self_contained(slp_path: Path) -> None:
    """Fail if a ``.slp`` depends on images stored outside it.

    Args:
        slp_path: Path to the ``.slp`` file.

    Raises:
        ValueError: If any video references an external path, naming the file and the
            paths it depends on.
    """
    external = _external_references(slp_path)
    if not external:
        return
    listed = "\n  ".join(external[:10])
    more = f"\n  ... and {len(external) - 10} more" if len(external) > 10 else ""
    raise ValueError(
        f"{slp_path} is not self-contained: it references {len(external)} image path(s) "
        f"outside itself:\n  {listed}{more}\nA package like this breaks when those paths "
        "become unreachable, and the standard repair — re-saving the embedded subset — "
        "permanently caps the label set at whatever was embedded at repair time. Rebuild "
        "it rather than publishing it."
    )
