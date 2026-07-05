"""Producer lineage recorded into the wandb seed run config (not per-artifact).

Every seed run records where the published artifacts came from: this repo's git SHA,
the exact matrix content hash, the source/snapshot provenance, and the tool/contract
versions. Per-artifact metadata stays exactly the six selection keys; all lineage
lives here in the run config.
"""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
from pathlib import Path
from typing import Optional

#: Provenance of the committed selection matrix.
SELECTION_MATRIX_SOURCE = (
    "https://gitlab.com/salk-tm/models-downloader "
    "(tests/data/models_downloader_input/20250204_models/model_chooser_table.xlsx)"
)
SELECTION_MATRIX_DATE = "2026-07-04"
MODELS_SNAPSHOT = "20250204"

_GIT_SHA_ENV = "SLEAP_ROOTS_TRAINING_GIT_SHA"


def _git_root() -> Optional[Path]:
    """Return the ``.git`` repo root anchored at this package, or ``None``.

    Walks up from this file (never the current working directory, which may be an
    unrelated repository).
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return None


def _pkg_version(name: str) -> str:
    """Return an installed package version, or ``"unknown"`` if not installed."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _resolve_git_sha() -> str:
    """Resolve this repo's git SHA robustly; never raise.

    Order: explicit ``SLEAP_ROOTS_TRAINING_GIT_SHA`` override, then ``git rev-parse``
    against a ``.git`` anchored at the package (suffixing ``+dirty`` when the tree is
    dirty), then the package version, then ``"unknown"``.

    Returns:
        The resolved SHA string (or fallback sentinel).
    """
    override = os.environ.get(_GIT_SHA_ENV)
    if override:
        return override
    root = _git_root()
    if root is not None:
        try:
            sha = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip()
            dirty = bool(
                subprocess.run(
                    ["git", "-C", str(root), "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5,
                ).stdout.strip()
            )
            return sha + ("+dirty" if dirty else "")
        except (subprocess.SubprocessError, OSError):
            pass
    version = _pkg_version("sleap-roots-training")
    return f"v{version}" if version != "unknown" else "unknown"


def build_lineage(matrix_sha256: str) -> dict:
    """Build the run-config lineage record for a seed.

    Args:
        matrix_sha256: SHA256 of the loaded selection matrix content, so the exact
            inputs are pinned independently of git cleanliness.

    Returns:
        A flat lineage mapping suitable for ``wandb.init(config=...)``.
    """
    git_sha = _resolve_git_sha()
    return {
        "git_sha": git_sha,
        "git_dirty": git_sha.endswith("+dirty"),
        "matrix_content_sha256": matrix_sha256,
        "selection_matrix_source": SELECTION_MATRIX_SOURCE,
        "selection_matrix_date": SELECTION_MATRIX_DATE,
        "models_snapshot": MODELS_SNAPSHOT,
        "sleap_roots_training_version": _pkg_version("sleap-roots-training"),
        "wandb_version": _pkg_version("wandb"),
        "sleap_roots_contracts_version": _pkg_version("sleap-roots-contracts"),
    }
