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
    logged = run.log_artifact(artifact)
    logged.wait()  # wait before linking, or the link can race.
    target = f"{cfg.registry_project()}/{collection}"
    run.link_artifact(logged, target, aliases=[cfg.alias])


def _existing_collections(api, project: str) -> set:
    """Return the set of model-collection names that exist under ``project``.

    Listing existing collections up front lets the idempotency check distinguish
    "collection absent" (expected on a first seed) from a real API/network error
    without swallowing the latter — a swallowed read error would be treated as
    "not yet production" and wrongly re-publish, moving the ``production`` alias.
    """
    return {
        collection.name
        for collection in api.artifact_collections(
            project_name=project, type_name="model"
        )
    }


def _collection_has_production(api, project: str, collection: str, alias: str) -> bool:
    """Return whether an existing ``collection`` holds an artifact with ``alias``.

    The caller MUST have confirmed the collection exists (see ``_existing_collections``)
    — for an existing collection ``api.artifacts`` does not raise "not found", so any
    error here propagates (fail closed) rather than being mistaken for "no production".
    """
    name = f"{project}/{collection}"
    return any(
        alias in (getattr(artifact, "aliases", None) or [])
        for artifact in api.artifacts(type_name="model", name=name)
    )


def resolve_all(
    cards: Iterable[Card], models_root: Path, checksums: Mapping[str, str]
) -> list:
    """Resolve every card's model directory (validate-all before any publish).

    Raises on the first unresolvable card, so a resolution error can never leave a
    partial production seed. Runs no network — safe to call before ``wandb.init``.

    Args:
        cards: The cards to resolve.
        models_root: Directory of ``<model_id>.zip`` archives.
        checksums: Map of ``model_id`` to source-zip SHA256.

    Returns:
        A list of ``(card, model_dir)`` pairs, in order.
    """
    return [
        (
            card,
            resolve_model_dir(
                card.source_model_id, models_root, checksums, require_pinned=True
            ),
        )
        for card in cards
    ]


def seed_registry(
    resolved: Iterable,
    cfg: RegistryConfig,
    run,
    *,
    api=None,
    force: bool = False,
) -> dict:
    """Publish already-resolved cards to the registry, idempotently.

    Skips collections that already carry the production alias unless ``force`` is set
    (so a re-run is a no-op and resumes after a partial failure); a real API error
    during the idempotency read propagates (fail closed) rather than causing a
    duplicate publish.

    Args:
        resolved: ``(card, model_dir)`` pairs from :func:`resolve_all`.
        cfg: The resolved registry configuration.
        run: The active ``wandb`` run.
        api: A ``wandb.Api`` (created lazily if ``None``) for the idempotency read.
        force: If true, re-publish and re-point the alias even when already seeded.

    Returns:
        A report ``{"published": [...], "skipped": [...]}``.

    Raises:
        ValueError: On a duplicate collection id in the seed set.
    """
    resolved = list(resolved)
    ids = [collection_id(card) for card, _ in resolved]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate collection ids in the seed set: {duplicates}")

    if api is None:
        import wandb

        api = wandb.Api()

    project = cfg.registry_project()
    existing = set() if force else _existing_collections(api, project)
    published: list = []
    skipped: list = []
    for card, model_dir in resolved:
        collection = collection_id(card)
        already = (
            not force
            and collection in existing
            and _collection_has_production(api, project, collection, cfg.alias)
        )
        if already:
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
    existing = _existing_collections(api, project)
    present: list = []
    missing: list = []
    for collection in expected_collections:
        if collection in existing and _collection_has_production(
            api, project, collection, cfg.alias
        ):
            present.append(collection)
        else:
            missing.append(collection)
    return {"present": sorted(present), "missing": sorted(missing)}
