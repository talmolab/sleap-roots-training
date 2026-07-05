"""Expand selection rows into per-species, per-root-type production cards.

Each selection row expands to one card per non-empty root-type model, carrying that
row's own species/mode/age window. A model shared across species (or across a
species' two cylinder-family modes) therefore yields one card per row it appears in,
each with its own selection metadata but the same ``source_model_id`` — which is what
the ``sleap-roots-predict`` matcher (filtering ``species ==`` / ``mode ==`` / age)
requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sleap_roots_training.registry.chooser import SelectionRow, parse_age_window

#: The three root types, in the order their slots appear on a selection row.
_ROOT_SLOTS = ("primary", "lateral", "crown")


@dataclass(frozen=True)
class Card:
    """One production selection card: a matchable (species, mode, age, root) unit.

    Attributes:
        species: The species this card selects for.
        mode: The imaging mode (raw, space preserved).
        age_min: Inclusive lower bound of the contiguous age window.
        age_max: Inclusive upper bound of the contiguous age window.
        root_type: One of ``"primary"``, ``"lateral"``, ``"crown"``.
        source_model_id: The shared physical model id backing this card.
    """

    species: str
    mode: str
    age_min: int
    age_max: int
    root_type: str
    source_model_id: str


def expand_rows_to_cards(rows: Iterable[SelectionRow]) -> list[Card]:
    """Expand selection rows into one card per non-empty root-type model.

    Args:
        rows: The selection rows to expand.

    Returns:
        The expanded cards, in row-then-root-slot order.
    """
    result: list[Card] = []
    for row in rows:
        age_min, age_max = parse_age_window(row.age)
        model_ids = {
            "primary": row.primary_model_id,
            "lateral": row.lateral_model_id,
            "crown": row.crown_model_id,
        }
        for root_type in _ROOT_SLOTS:
            model_id = model_ids[root_type]
            if model_id is None:
                continue
            result.append(
                Card(
                    species=row.species,
                    mode=row.mode,
                    age_min=age_min,
                    age_max=age_max,
                    root_type=root_type,
                    source_model_id=model_id,
                )
            )
    return result


def card_to_metadata(card: Card) -> dict:
    """Build the flat wandb-artifact metadata for a card.

    Returns exactly the selection dimensions the consumer reads plus the
    non-contract ``source_model_id`` for traceability. It deliberately omits the
    wandb-intrinsic keys (``registry_id`` / ``version`` / ``weights_checksum``),
    which the consumer injects from the artifact, and preserves ``mode`` verbatim
    (the space in ``"multiplant cylinder"`` is kept — only ``collection_id`` slugs it).

    Args:
        card: The card to describe.

    Returns:
        The flat metadata mapping (validates against ``ModelCard``).
    """
    return {
        "species": card.species,
        "mode": card.mode,
        "age_min": card.age_min,
        "age_max": card.age_max,
        "root_type": card.root_type,
        "source_model_id": card.source_model_id,
    }


def collection_id(card: Card) -> str:
    """Return the per-card registry collection id.

    The id encodes the full selection tuple so every card maps to its own
    collection (which lets the ``production`` alias be unique per collection).
    Spaces in ``mode`` become hyphens for the collection name only.

    Args:
        card: The card to name.

    Returns:
        A string like ``"rice-cylinder-crown-age6-10"``.
    """
    mode_slug = card.mode.replace(" ", "-")
    return (
        f"{card.species}-{mode_slug}-{card.root_type}"
        f"-age{card.age_min}-{card.age_max}"
    )
