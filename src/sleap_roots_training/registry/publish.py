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


def publish_card(
    run, card: Card, model_dir: Path, cfg: RegistryConfig, *, api=None
) -> str:
    """Publish one card as a ``type="model"`` artifact linked as production.

    After linking, this reads back **the server's own view** of the metadata and
    refreshes it in place if it is stale. That check is not belt-and-braces: artifact
    metadata is not part of the manifest digest, and ``log_artifact`` no-ops on an
    unchanged digest, so re-publishing byte-identical weights can leave the *previous*
    metadata live while the report says "published". ``--force`` does not close this —
    it bypasses only the idempotency read, and cannot create a new version while the
    digest is unchanged.

    The read-back needs no extra query: ``run.link_artifact`` already returns a
    membership-backed artifact carrying ``metadata`` and ``digest``, which this code
    previously discarded. (Do not resolve it through ``Artifact._from_id``, which
    returns a process-cached instance and would read back our own local view.)

    Args:
        run: The active ``wandb`` run.
        card: The card to publish.
        model_dir: The resolved (junk-free) model directory to add.
        cfg: The resolved registry configuration.
        api: A ``wandb.Api`` used to **re-read** the metadata after a refresh. Without
            it the refresh cannot be confirmed, so the result is reported optimistically
            rather than as a failure the operator cannot act on.

    Returns:
        ``"published"``, or ``"failed"`` if the metadata could not be made current.
    """
    import wandb  # lazy: only the network path needs wandb.

    collection = collection_id(card)
    metadata = card_to_metadata(card)
    artifact = wandb.Artifact(name=collection, type="model", metadata=metadata)
    artifact.add_dir(str(model_dir))
    logged = run.log_artifact(artifact)
    logged.wait()  # wait before linking, or the link can race.
    target = f"{cfg.registry_project()}/{collection}"
    linked = run.link_artifact(logged, target, aliases=[cfg.alias])

    # An older wandb, or a fake, may return nothing from link_artifact. Nothing to
    # read back from, so nothing to assert -- treat as published rather than inventing
    # a failure the operator cannot act on.
    if linked is None or not hasattr(linked, "metadata"):
        return "published"

    if _is_selectors_shape(linked.metadata):
        return "published"

    logger.info("refreshing stale metadata on %s", collection)
    linked.metadata = metadata
    linked.save()  # updateArtifact; NOT a re-log, which cannot make a new version

    # Re-read the SERVER's view. Checking `linked.metadata` here would be worthless: we
    # just assigned it, so it reports our own local value whether or not the write
    # landed. Without an api there is nothing to re-read from, so do not manufacture a
    # failure -- the offline path cannot confirm the refresh either way.
    if api is None:
        return "published"
    fresh = _aliased_artifact(api, cfg.registry_project(), collection, cfg.alias)
    if fresh is None or _is_selectors_shape(getattr(fresh, "metadata", None)):
        return "published"
    logger.warning("metadata on %s did not refresh", collection)
    return "failed"


#: The card-level selection keys the reshape removed. Their presence means a blob was
#: written by the old producer (or is a half-migrated write), whichever shape it also has.
_LEGACY_CARD_KEYS = frozenset({"species", "mode", "age_min", "age_max"})


def _is_selectors_shape(metadata) -> bool:
    """Return whether ``metadata`` is the current one-card-per-physical-model shape.

    Deliberately **structural**, never ``ModelCard.model_validate``: a contract with a
    tolerant read would validate the legacy blob fine, so a validation-based check would
    report every stale collection as current — the exact failure this exists to catch.
    """
    if not isinstance(metadata, Mapping):
        return False
    if not metadata.get("selectors"):
        return False
    return not (_LEGACY_CARD_KEYS & set(metadata))


def _existing_collections(api, project: str) -> dict:
    """Return the existing model collections under ``project``, keyed by name.

    Listing existing collections up front lets the idempotency check distinguish
    "collection absent" (expected on a first seed) from a real API/network error
    without swallowing the latter — a swallowed read error would be treated as
    "not yet production" and wrongly re-publish, moving the ``production`` alias.

    The collection **objects** are kept rather than reduced to a set of names, because
    orphan reporting needs ``ArtifactCollection.aliases`` — one lightweight query per
    collection, as against paginating every version of every collection at 50/page.
    That distinction is load-bearing: the registry holds far more collections than
    cards, most of them sweep/run artifacts.
    """
    return {
        collection.name: collection
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
    # The id is derived from `source_model_id` via a lossy slug (`/` and `=` both map
    # to `-`), so two models differing only there collapse onto one collection. Report
    # the offending MODELS, not just the collapsed id -- an operator cannot act on
    # "x-y" alone.
    owners: dict[str, list[str]] = {}
    for card, _ in resolved:
        owners.setdefault(collection_id(card), []).append(card.source_model_id)
    duplicates = {
        cid: sorted(models) for cid, models in owners.items() if len(models) > 1
    }
    if duplicates:
        detail = "; ".join(
            f"{cid!r} <- {models}" for cid, models in sorted(duplicates.items())
        )
        raise ValueError(f"duplicate collection ids in the seed set: {detail}")

    if api is None:
        import wandb

        api = wandb.Api()

    project = cfg.registry_project()
    existing = {} if force else _existing_collections(api, project)
    published: list = []
    skipped: list = []
    failed: list = []
    stale: list = []

    # Echo per collection as it happens. `logger.info` alone is invisible (nothing in
    # the package configures logging) and the caller's final echo is never reached if
    # something propagates -- after a failure at card 5 of 8 the operator would have no
    # local record of which collections now carry `production`.
    def _emit(outcome: str, collection: str) -> None:
        print(f"{outcome}: {collection}", flush=True)

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
            # The skip path is the DEFAULT on every re-run, so a half-migrated
            # collection would otherwise sit here undetected: a check scoped to
            # `published` never sees it.
            if not _aliased_metadata_is_current(api, project, collection, cfg.alias):
                stale.append(collection)
                _emit("skipped (STALE metadata)", collection)
            else:
                _emit("skipped", collection)
            continue
        logger.info("publish %s", collection)
        try:
            outcome = publish_card(run, card, model_dir, cfg, api=api)
        except (
            Exception
        ) as error:  # noqa: BLE001 - one bad card must not abort the seed
            logger.warning("publish %s failed: %s", collection, error)
            failed.append(collection)
            _emit(f"FAILED ({error})", collection)
            continue
        if outcome == "failed":
            failed.append(collection)
            _emit("FAILED (metadata did not refresh)", collection)
        else:
            published.append(collection)
            _emit("published", collection)
    return {
        "published": published,
        "skipped": skipped,
        "failed": failed,
        "stale": stale,
    }


def _aliased_metadata_is_current(
    api, project: str, collection: str, alias: str
) -> bool:
    """Return whether the aliased artifact in ``collection`` carries the current shape.

    A read failure counts as *current* rather than stale: this runs on the skip path of
    an otherwise-successful re-run, and turning a transient read error into a reported
    migration failure would be a false alarm the operator cannot act on.
    """
    name = f"{project}/{collection}"
    try:
        for artifact in api.artifacts(type_name="model", name=name):
            if alias in (getattr(artifact, "aliases", None) or []):
                return _is_selectors_shape(getattr(artifact, "metadata", None))
    except Exception:  # noqa: BLE001 - see docstring
        return True
    return True


def verify_registry(
    cfg: RegistryConfig,
    expected_collections: Iterable[str],
    api=None,
    *,
    report_orphans: bool = True,
) -> dict:
    """Re-run the consumer read path and report the live registry against the matrix.

    Uses the same registry project string the consumer uses (not the seed run's
    project). Reports, but never acts on, collections the matrix no longer produces:
    retiring them is a separate step gated on the upgraded consumer being deployed, so
    this deletes nothing and moves no alias.

    Args:
        cfg: The resolved registry configuration.
        expected_collections: The collection ids that should be present.
        api: A ``wandb.Api`` (created lazily if ``None``).
        report_orphans: When false (set under ``--only``), skip orphan reporting —
            ``--only`` scopes the expected set, so every out-of-scope collection would
            otherwise be reported as an orphan.

    Returns:
        A report with ``present`` / ``missing`` / ``legacy`` / ``orphans`` /
        ``indeterminate`` (all sorted) and ``orphans_suppressed``. Use
        :func:`verify_failed` for the exit code rather than reading the buckets.
    """
    if api is None:
        import wandb

        api = wandb.Api()

    project = cfg.registry_project()
    existing = _existing_collections(api, project)
    expected = list(expected_collections)
    present: list = []
    missing: list = []
    legacy: list = []
    for collection in expected:
        if collection not in existing:
            missing.append(collection)
            continue
        aliased = _aliased_artifact(api, project, collection, cfg.alias)
        if aliased is None:
            missing.append(collection)
            continue
        present.append(collection)
        # Without this a collection an upgraded consumer cannot read is reported
        # `present`, and there is no re-runnable way to ask whether the registry is
        # actually migrated.
        if not _is_selectors_shape(getattr(aliased, "metadata", None)):
            legacy.append(collection)

    orphans: list = []
    indeterminate: list = []
    if report_orphans:
        for name, collection in existing.items():
            if name in set(expected):
                continue
            try:
                aliases = collection.aliases
            except Exception:  # noqa: BLE001 - unknown is not the same as broken
                indeterminate.append(name)
                continue
            if cfg.alias in (aliases or []):
                orphans.append(name)

    return {
        "present": sorted(present),
        "missing": sorted(missing),
        "legacy": sorted(legacy),
        "orphans": sorted(orphans),
        "indeterminate": sorted(indeterminate),
        "orphans_suppressed": not report_orphans,
    }


def _aliased_artifact(api, project: str, collection: str, alias: str):
    """Return the ``alias``-carrying artifact in ``collection``, or ``None``."""
    name = f"{project}/{collection}"
    for artifact in api.artifacts(type_name="model", name=name):
        if alias in (getattr(artifact, "aliases", None) or []):
            return artifact
    return None


def verify_failed(report: Mapping) -> bool:
    """Return whether a ``verify_registry`` report should exit non-zero.

    Orphans and indeterminate collections deliberately do **not** fail: an orphan is
    expected for the whole migration window, and an unreadable collection is unknown
    rather than broken. A missing alias or a legacy shape on an **expected** collection
    does fail — those are collections the consumer needs and cannot use.
    """
    return bool(report.get("missing") or report.get("legacy"))
