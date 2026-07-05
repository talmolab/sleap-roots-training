"""Publish, link, and verify production model artifacts in the wandb registry.

This is the thin network layer. It publishes each card as a ``type="model"`` artifact
with exactly the card's selection metadata, links it into a per-card collection under
the configured registry with the ``production`` alias, and can re-run the consumer
read path to verify the alias landed. ``wandb`` is imported lazily so the pure-logic
and dry-run paths never require it loaded.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Mapping, Optional

from sleap_roots_training.registry.cards import (
    Card,
    card_to_metadata,
    collection_id,
)
from sleap_roots_training.registry.config import RegistryConfig
from sleap_roots_training.registry.models import resolve_model_dir

logger = logging.getLogger(__name__)


def publish_card(run, card: Card, model_dir: Path, cfg: RegistryConfig) -> None:
    """Publish one card as a ``type="model"`` artifact linked as production.

    Args:
        run: The active ``wandb`` run.
        card: The card to publish.
        model_dir: The resolved (junk-free) model directory to add.
        cfg: The resolved registry configuration.
    """
    import wandb  # lazy: only the network path needs wandb.

    collection = collection_id(card)
    artifact = wandb.Artifact(
        name=collection, type="model", metadata=card_to_metadata(card)
    )
    artifact.add_dir(str(model_dir))
    logged = run.log_artifact(artifact, type="model")
    logged.wait()  # wait before linking, or the link can race.
    target = f"{cfg.registry_project()}/{collection}"
    run.link_artifact(logged, target, aliases=[cfg.alias])


def _collection_has_production(api, project: str, collection: str, alias: str) -> bool:
    """Return whether ``collection`` already holds an artifact with ``alias``."""
    name = f"{project}/{collection}"
    try:
        artifacts = api.artifacts(type_name="model", name=name)
    except Exception:  # noqa: BLE001 - a missing collection is simply "no production".
        return False
    for artifact in artifacts:
        if alias in (getattr(artifact, "aliases", None) or []):
            return True
    return False


def seed_registry(
    cards: Iterable[Card],
    models_root: Path,
    checksums: Mapping[str, str],
    cfg: RegistryConfig,
    run,
    *,
    api=None,
    force: bool = False,
    only: Optional[Iterable[str]] = None,
) -> dict:
    """Publish every (in-scope) card to the registry, idempotently.

    Validates that all in-scope cards resolve before publishing any (so a resolution
    error can't leave a partial production seed), skips collections that already carry
    the production alias unless ``force`` is set, and supports an ``only`` filter for
    canary seeding.

    Args:
        cards: The full expanded card set.
        models_root: Directory of ``<model_id>.zip`` archives.
        checksums: Map of ``model_id`` to source-zip SHA256.
        cfg: The resolved registry configuration.
        run: The active ``wandb`` run.
        api: A ``wandb.Api`` (created lazily if ``None``) used for the idempotency read.
        force: If true, re-publish and re-point the alias even when already seeded.
        only: If given, restrict both validation and publishing to these collection ids.

    Returns:
        A report ``{"published": [...], "skipped": [...]}``.

    Raises:
        ValueError: On an unknown ``only`` id or a duplicate collection id.
    """
    cards = list(cards)
    selected = cards
    if only is not None:
        only_set = set(only)
        known = {collection_id(c) for c in cards}
        unknown = only_set - known
        if unknown:
            raise ValueError(f"--only names unknown collection(s): {sorted(unknown)}")
        selected = [c for c in cards if collection_id(c) in only_set]

    ids = [collection_id(c) for c in selected]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate collection ids in the seed set: {duplicates}")

    # Validate-all-before-publish: resolve every in-scope card first.
    resolved: list[tuple[Card, Path]] = []
    for card in selected:
        model_dir = resolve_model_dir(
            card.source_model_id, models_root, checksums, require_pinned=True
        )
        resolved.append((card, model_dir))

    if api is None:
        import wandb

        api = wandb.Api()

    project = cfg.registry_project()
    published: list[str] = []
    skipped: list[str] = []
    for card, model_dir in resolved:
        collection = collection_id(card)
        if not force and _collection_has_production(
            api, project, collection, cfg.alias
        ):
            logger.info("skip %s (already production)", collection)
            skipped.append(collection)
            continue
        logger.info("publish %s", collection)
        publish_card(run, card, model_dir, cfg)
        published.append(collection)
    return {"published": published, "skipped": skipped}


def verify_registry(
    cfg: RegistryConfig, expected_collections: Iterable[str], api=None
) -> dict:
    """Re-run the consumer read path and report alias presence per collection.

    Uses the same registry project string the consumer uses (not the seed run's
    project).

    Args:
        cfg: The resolved registry configuration.
        expected_collections: The collection ids that should be present.
        api: A ``wandb.Api`` (created lazily if ``None``).

    Returns:
        A report ``{"present": [...], "missing": [...]}`` (sorted).
    """
    if api is None:
        import wandb

        api = wandb.Api()

    project = cfg.registry_project()
    existing = {
        collection.name
        for collection in api.artifact_collections(
            project_name=project, type_name="model"
        )
    }
    present: list[str] = []
    missing: list[str] = []
    for collection in expected_collections:
        if collection in existing and _collection_has_production(
            api, project, collection, cfg.alias
        ):
            present.append(collection)
        else:
            missing.append(collection)
    return {"present": sorted(present), "missing": sorted(missing)}
