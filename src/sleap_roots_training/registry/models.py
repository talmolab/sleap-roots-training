"""Resolve a card's model id to a usable, snapshot-pinned model directory.

The canonical ``models-downloader`` snapshot ships each model as ``<model_id>.zip``.
The production path verifies the archive against the SHA256 recorded in the committed
matrix, then extracts it (OS-junk filtered) into a fresh temp/cache directory with a
canonical layout — pinning the snapshot so the published ``weights_checksum`` is
deterministic. An already-unzipped directory is accepted only as a dev/dry-run
convenience (it is not snapshot-pinned).
"""

from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Mapping, Optional

#: File names required for legacy-model inference.
ESSENTIAL_FILES = ("best_model.h5", "training_config.json")

_JUNK_BASENAMES = {".DS_Store", "Thumbs.db"}
_CACHE_ROOT: Optional[Path] = None


def _is_junk(member_name: str) -> bool:
    """Return whether a zip member is OS-generated junk to be excluded."""
    parts = member_name.replace("\\", "/").split("/")
    if any(part == "__MACOSX" for part in parts):
        return True
    base = parts[-1]
    return base in _JUNK_BASENAMES or base.endswith("Zone.Identifier")


def junk_filter(names: Iterable[str]) -> list[str]:
    """Return the non-junk names, sorted (deterministic).

    Args:
        names: Candidate member/file names.

    Returns:
        The names that are not OS junk, in sorted order.
    """
    return sorted(name for name in names if not _is_junk(name))


def _sha256_of_file(path: Path) -> str:
    """Return the hex SHA256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_cache_root() -> Path:
    """Return a process-wide temp cache root for extracted models (auto-cleaned)."""
    global _CACHE_ROOT
    if _CACHE_ROOT is None:
        _CACHE_ROOT = Path(tempfile.mkdtemp(prefix="srt-models-"))
        atexit.register(shutil.rmtree, _CACHE_ROOT, ignore_errors=True)
    return _CACHE_ROOT


def _locate_model_root(root: Path) -> Path:
    """Return the directory that holds ``best_model.h5`` within ``root``.

    Snapshot zips are inconsistent: some hold ``best_model.h5`` at the archive
    root, others wrap it in an inner ``<model>/`` directory. Normalizing to the
    directory that actually contains the weights keeps the ``add_dir`` layout (and
    thus the published digest) canonical across both forms. Prefers the shallowest
    match (so a root-level copy wins over a nested one). Falls back to ``root`` if
    the weights are absent (so ``_verify_essentials`` raises a clear error).
    """
    matches = list(root.rglob("best_model.h5"))
    if not matches:
        return root
    return min(matches, key=lambda p: (len(p.relative_to(root).parts), str(p))).parent


def _verify_essentials(model_dir: Path, model_id: str) -> None:
    """Raise if ``model_dir`` lacks an essential inference file."""
    for name in ESSENTIAL_FILES:
        if not (model_dir / name).is_file():
            raise ValueError(
                f"{model_id}: resolved model dir is missing {name} "
                f"(expected at {model_dir / name})"
            )


def _extract_junk_free(zip_path: Path, dest: Path) -> None:
    """Extract ``zip_path`` into ``dest``, omitting OS-junk members."""
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members = [info for info in archive.infolist() if not _is_junk(info.filename)]
        # extractall sanitizes member paths (Zip-Slip-safe) on Python 3.6.2+.
        archive.extractall(dest, members=members)


def _extract_atomic(zip_path: Path, dest: Path) -> None:
    """Extract into a sibling temp dir, then rename to ``dest`` (atomic).

    A crash mid-extraction leaves only the temp dir, so ``dest`` is never a
    half-populated tree that a later run would wrongly reuse.
    """
    tmp = dest.with_name(f"{dest.name}.tmp-{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    _extract_junk_free(zip_path, tmp)
    try:
        tmp.rename(dest)
    except OSError:
        # Another call populated dest first; discard our copy.
        shutil.rmtree(tmp, ignore_errors=True)


def resolve_model_dir(
    model_id: str,
    models_root: Path,
    checksums: Mapping[str, str],
    *,
    require_pinned: bool = False,
    cache_root: Optional[Path] = None,
) -> Path:
    """Resolve a model id to a usable model directory under ``models_root``.

    Args:
        model_id: Relative model id (e.g. ``"soybean/primary/…n=1389"``).
        models_root: Directory containing ``<model_id>.zip`` and/or ``<model_id>/``.
        checksums: Map of ``model_id`` to the SHA256 of its source ``.zip``.
        require_pinned: If true (real writes), reject the unpinned already-unzipped
            directory form so production seeds always use the SHA256-pinned archive.
        cache_root: Directory to extract archives into (defaults to a temp dir).

    Returns:
        Path to the resolved model directory.

    Raises:
        FileNotFoundError: If neither a ``.zip`` nor a directory exists for the id.
        ValueError: On a missing recorded checksum, a checksum mismatch, a missing
            essential file, or an unpinned directory when ``require_pinned`` is set.
    """
    models_root = Path(models_root)
    zip_path = models_root / f"{model_id}.zip"
    dir_path = models_root / model_id

    if zip_path.is_file():
        expected = checksums.get(model_id)
        if not expected:
            raise ValueError(f"{model_id}: no SHA256 recorded in the selection matrix")
        actual = _sha256_of_file(zip_path)
        if actual != expected:
            raise ValueError(
                f"{model_id}: archive SHA256 mismatch "
                f"(recorded {expected}, got {actual})"
            )
        # Content-keyed leaf: short (avoids the Windows MAX_PATH blow-up of
        # extracting under the deep, sometimes-doubled model id) and
        # self-invalidating (a changed zip -> new digest -> new dir, never stale).
        base = Path(cache_root) if cache_root is not None else _default_cache_root()
        dest = base / actual[:16]
        if not dest.exists():
            _extract_atomic(zip_path, dest)
        model_dir = _locate_model_root(dest)
        _verify_essentials(model_dir, model_id)
        return model_dir

    if dir_path.is_dir():
        if require_pinned:
            raise ValueError(
                f"{model_id}: resolved as an already-unzipped directory, which is "
                f"NOT snapshot-pinned; provide the <model_id>.zip archive for --execute"
            )
        model_dir = _locate_model_root(dir_path)
        _verify_essentials(model_dir, model_id)
        return model_dir

    raise FileNotFoundError(
        f"{model_id}: no '{model_id}.zip' or '{model_id}/' under {models_root}"
    )
