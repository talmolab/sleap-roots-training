"""Producer lineage recorded into the wandb seed run config (not per-artifact).

Every seed run records where the artifacts in its scope came from: this repo's git SHA,
the exact matrix content hash, each in-scope row's `source` and each in-scope model's
origin (read from the matrix, never from constants here, because rows and models come
from more than one place), and the tool/contract versions. Per-artifact metadata stays
exactly the card's selection keys; all lineage lives here in the run config.
"""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sleap_roots_training.registry.cards import Card
    from sleap_roots_training.registry.chooser import SelectionMatrix
    from sleap_roots_training.registry.config import RegistryConfig

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


def resolve_git_sha() -> str:
    """Resolve this repo's git SHA robustly; never raise.

    Order: explicit ``SLEAP_ROOTS_TRAINING_GIT_SHA`` override, then ``git rev-parse``
    against a ``.git`` anchored at the package (suffixing ``+dirty`` when the tree is
    dirty), then the package version, then ``"unknown"``.

    Public because a package's provenance stamps the same code version a model's lineage
    does (third blocking review of #40): :mod:`~sleap_roots_training.labeling.package` was
    importing this under its former private name, so a refactor here would have broken it
    without looking like a breaking change from this module's side.

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


def build_lineage(
    matrix_sha256: str,
    cards: Iterable[Card],
    matrix: SelectionMatrix,
    cfg: RegistryConfig,
) -> dict:
    """Build the run-config lineage record for a seed.

    Provenance is scoped to ``cards`` — the invocation's scope, published or skipped —
    so a run under ``--only`` does not claim provenance for collections it never touched.
    Both provenance fields are lists of records rather than mappings keyed by model id,
    because model ids contain ``/``, ``=`` and ``.``; as values they stay out of the way
    of however wandb treats those characters in config keys.

    Args:
        matrix_sha256: SHA256 of the loaded selection matrix content, so the exact
            inputs are pinned independently of git cleanliness.
        cards: The run's in-scope cards.
        matrix: The loaded selection matrix the cards were expanded from.
        cfg: The registry target the run links under. Recorded because a candidate
            publish and its later promotion are otherwise the same shape: the alias a
            run linked is what says which one made the cards live.

    Returns:
        A lineage mapping suitable for ``wandb.init(config=...)``: ``row_sources`` (one
        ``{species, mode, age, source}`` per row backing an in-scope card, in file order)
        and ``model_origins`` (one ``{model_id, snapshot, location, pinned_by}`` per
        in-scope model, sorted by id) and ``registry_target`` (entity, registry and
        alias), alongside the git and version keys.
    """
    in_scope = {(card.source_model_id, card.root_type) for card in cards}
    # A row backs a card when it names the card's model in the card's root-type slot.
    row_sources = [
        {"species": row.species, "mode": row.mode, "age": row.age, "source": row.source}
        for row in matrix.rows
        if any(
            row.model_ids()[root_type] == model_id for model_id, root_type in in_scope
        )
    ]
    model_origins = [
        {
            "model_id": model_id,
            "snapshot": matrix.origins[model_id].snapshot,
            "location": matrix.origins[model_id].location,
            "pinned_by": matrix.origins[model_id].pinned_by,
        }
        for model_id in sorted({model_id for model_id, _ in in_scope})
    ]
    git_sha = resolve_git_sha()
    return {
        "git_sha": git_sha,
        "git_dirty": git_sha.endswith("+dirty"),
        "matrix_content_sha256": matrix_sha256,
        "row_sources": row_sources,
        "model_origins": model_origins,
        "registry_target": {
            "entity": cfg.entity,
            "registry": cfg.registry,
            "alias": cfg.alias,
        },
        "sleap_roots_training_version": _pkg_version("sleap-roots-training"),
        "wandb_version": _pkg_version("wandb"),
        "sleap_roots_contracts_version": _pkg_version("sleap-roots-contracts"),
    }
