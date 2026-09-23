r"""Decide what a path is allowed to look like once it leaves the scan.

This is a whitelist. A candidate path is emitted relative to the supplied discovery
root, with the root itself rendered as one fixed token; a referenced video path is
emitted as its filename alone. Nothing else gets out, so nothing above the root and no
directory chain recorded on another machine can reach an artifact.

It replaces a blacklist that leaked on the two real paths it was written for. Those
markers were slash-terminated (``users/``, ``Users/``, ``home/``) while Windows SLEAP
records video paths with backslashes; relative and ``..``-rooted paths had no rule at
all; ``pathlib`` folds ``\\\\server\\share`` into the anchor, so a person-named share
survived a "first segment" rule; and ``home/`` matched inside words like ``genome``. A
blacklist over arbitrary recorded strings cannot be shown complete. This can.

``scripts/pull_tf_reference.py``'s ``_REDACTIONS`` is deliberately **not** reused as a
floor: it is a case-sensitive literal ``str.replace`` hardcoded to one person's name and
protects nobody else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TypeVar

#: Stands in for the discovery root in every emitted path.
ROOT_TOKEN = "<ROOT>"

#: Reason recorded when a candidate could not be expressed relative to the root.
OUTSIDE_ROOT = "outside-root"

#: Emitted when a recorded path carries no usable filename.
UNKNOWN_FILENAME = "<unknown>"

#: Both separators, always. The recorded strings are Windows-shaped whatever host runs
#: the scan, and ``PurePath`` is ``PurePosixPath`` on the Linux and macOS CI runners —
#: there, ``Z:/a/b`` has an empty drive and ``Z:`` as its first component, so a
#: platform-dependent rule would emit a name that a Windows run would have hidden.
_SEPARATORS = ("/", "\\")

_Mapping = TypeVar("_Mapping", bound=dict)


@dataclass(frozen=True)
class EmittedPath:
    """A path in the form it is allowed to appear in an artifact.

    Attributes:
        text: What gets written.
        outside_root: Whether the path lay outside the discovery root, in which case
            ``text`` is a bare filename.
        reason: Why it was reduced to a filename, or ``None``.
    """

    text: str
    outside_root: bool = False
    reason: Optional[str] = None


def basename(recorded: str) -> str:
    """Return the final component of a recorded path, splitting on both separators.

    Args:
        recorded: A path string from any operating system, absolute, relative, UNC or
            drive-rooted.

    Returns:
        The filename, or :data:`UNKNOWN_FILENAME` if there is not one.
    """
    text = (recorded or "").strip()
    for separator in _SEPARATORS:
        text = text.replace(separator, "\x00")
    parts = [part for part in text.split("\x00") if part and part not in {".", ".."}]
    if not parts:
        return UNKNOWN_FILENAME
    final = parts[-1]
    # A drive-rooted string with nothing after it, e.g. ``C:``.
    if final.endswith(":"):
        return UNKNOWN_FILENAME
    return final


def emit_video_path(recorded: str) -> str:
    """Return the only part of a referenced video path that may be emitted.

    Args:
        recorded: The path exactly as the labels file records it.

    Returns:
        Its filename, or :data:`UNKNOWN_FILENAME`.
    """
    return basename(recorded)


def emit_path(path: Path, root: Path) -> EmittedPath:
    """Express ``path`` relative to ``root``, or reduce it to a filename.

    Args:
        path: The candidate path, as found by the walk.
        root: The supplied discovery root.

    Returns:
        The emitted form. A path that cannot be expressed relative to the root is
        reduced to its filename rather than emitted whole — the operator supplied the
        root knowing what is under it, and made no such warrant about anything else.
    """
    absolute = Path(os.path.abspath(str(path)))
    anchor = Path(os.path.abspath(str(root)))
    try:
        relative = absolute.relative_to(anchor)
    except ValueError:
        return EmittedPath(
            text=basename(str(path)), outside_root=True, reason=OUTSIDE_ROOT
        )
    return EmittedPath(text=f"{ROOT_TOKEN}/{relative.as_posix()}")


def emit_fields(row: _Mapping) -> _Mapping:
    """Return the non-path fields of a row unchanged.

    ``genotype``, ``accession_id`` and ``experiment_name`` name plants and experiments,
    not people, and the report is useless without them. They are listed here so that
    over-redaction is a visible decision rather than a silent one.

    Args:
        row: The row's non-path fields.

    Returns:
        The same mapping, unchanged.
    """
    return row
