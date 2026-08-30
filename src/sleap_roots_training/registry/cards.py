"""Expand selection rows into one production card per physical model.

Rows that name the same ``source_model_id`` for the same root type collapse into a
single card whose ``selectors`` are those rows' own (species, mode, age) contexts, each
preserved verbatim. A model validated for several species is therefore **one** card with
several selectors rather than one registration per species, and a consumer matches it
when *some single* selector matches all of species, mode and age — never the cross
product, so a generalist model cannot advertise a combination nobody trained.

``root_type`` stays scalar because it is intrinsic to the weights: a primary-root model
is never also a lateral one, and :func:`expand_rows_to_cards` fails the seed if a future
matrix edit breaks that assumption. There is deliberately no card-level age window —
a card whose selectors span 2-13 and 2-14 advertises neither globally, so age must be
read off the *matching* selector.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from sleap_roots_contracts import Selector

from sleap_roots_training.registry.chooser import SelectionRow, parse_age_window

#: The three root types, in the order their slots appear on a selection row. Card emission
#: order does *not* follow from this — since #47 the result is sorted on
#: ``(source_model_id, root_type)`` — so this tuple is read only to walk a row's slots.
#:
#: Deliberately *not* ``get_args(RootType)``, though its members are exactly
#: ``chooser.ROOT_TYPE_VOCAB`` and a test holds them to that. It is indexed into a mapping
#: keyed by ``SelectionRow``'s three ``*_model_id`` fields, so it is really the *row's*
#: slot list: a contract that gained a fourth root type would not emit more cards here, it
#: would raise ``KeyError`` on a valid row. Membership is the contract's to own; which
#: slots a row carries is this repo's.
_ROOT_SLOTS = ("primary", "lateral", "crown")


#: Total order over selectors. A frozen pydantic ``Selector`` is hashable but **not**
#: orderable, so a bare ``sorted(selectors)`` raises ``TypeError``; and a set-based
#: dedupe left unsorted would salt the order with ``PYTHONHASHSEED``. Sorting on an
#: explicit key is what makes emitted metadata byte-identical across processes.
def _selector_key(selector: Selector) -> tuple[str, str, int, int]:
    return (selector.species, selector.mode, selector.age_min, selector.age_max)


@dataclass(frozen=True)
class Card:
    """One production card: a physical model plus every context it was validated for.

    Attributes:
        root_type: One of ``"primary"``, ``"lateral"``, ``"crown"`` — intrinsic to the
            weights, which is why it is scalar rather than per-selector.
        selectors: The (species, mode, age window) contexts this model serves,
            de-duplicated and in :func:`_selector_key` order. Never empty.
        source_model_id: The physical model id backing this card.
    """

    root_type: str
    selectors: tuple[Selector, ...]
    source_model_id: str


def expand_rows_to_cards(rows: Iterable[SelectionRow]) -> list[Card]:
    """Expand selection rows into one card per physical model.

    Args:
        rows: The selection rows to expand.

    Returns:
        The expanded cards, ordered by ``source_model_id`` then ``root_type`` so the
        result is independent of the order the rows arrived in.

    Raises:
        ValueError: If one model id appears under more than one root type (the design
            rests on ``root_type`` being intrinsic to the weights), or if two different
            models of the same root type claim an identical selector (which would put
            two production cards in front of one consumer request).
    """
    # (model_id, root_type) -> selectors, in first-seen order before the sort.
    collected: dict[tuple[str, str], list[Selector]] = {}
    root_types_by_model: dict[str, set[str]] = {}

    for row in rows:
        age_min, age_max = parse_age_window(row.age)
        selector = Selector(
            species=row.species, mode=row.mode, age_min=age_min, age_max=age_max
        )
        model_ids = {
            "primary": row.primary_model_id,
            "lateral": row.lateral_model_id,
            "crown": row.crown_model_id,
        }
        for root_type in _ROOT_SLOTS:
            model_id = model_ids[root_type]
            if model_id is None:
                continue
            collected.setdefault((model_id, root_type), []).append(selector)
            root_types_by_model.setdefault(model_id, set()).add(root_type)

    _reject_models_spanning_root_types(root_types_by_model)

    cards = [
        Card(
            root_type=root_type,
            # dict.fromkeys de-duplicates in insertion order; the sort then imposes the
            # explicit total order. Doing both means neither step has to be trusted alone.
            selectors=tuple(sorted(dict.fromkeys(selectors), key=_selector_key)),
            source_model_id=model_id,
        )
        for (model_id, root_type), selectors in collected.items()
    ]
    _reject_selector_collisions(cards)
    return sorted(cards, key=lambda card: (card.source_model_id, card.root_type))


def _reject_models_spanning_root_types(
    root_types_by_model: dict[str, set[str]],
) -> None:
    """Fail the seed if one physical model is registered under two root types."""
    straddling = {
        model_id: sorted(root_types)
        for model_id, root_types in root_types_by_model.items()
        if len(root_types) > 1
    }
    if straddling:
        detail = "; ".join(
            f"{model_id!r} in {root_types}"
            for model_id, root_types in sorted(straddling.items())
        )
        raise ValueError(
            "a model must resolve to exactly one root type, but "
            f"{detail} — one card cannot describe weights of two root types"
        )


def _reject_selector_collisions(cards: Iterable[Card]) -> None:
    """Fail the seed if two models of one root type claim the same selector.

    Under the previous scheme this was caught incidentally: the collection id was built
    from the selection tuple, so a shared selector produced a duplicate id and the
    duplicate-id guard rejected the pair. An id derived from ``source_model_id`` gives
    them distinct ids, so both would publish, both would take the production alias, and
    the consumer would find two matching production cards for one request.
    """
    owners: dict[tuple[str, str, str, int, int], list[str]] = {}
    for card in cards:
        for selector in card.selectors:
            key = (card.root_type,) + _selector_key(selector)
            owners.setdefault(key, []).append(card.source_model_id)

    collisions = {
        key: sorted(models) for key, models in owners.items() if len(models) > 1
    }
    if collisions:
        detail = "; ".join(
            f"{key[0]} selector {key[1:]} claimed by {models}"
            for key, models in sorted(collisions.items())
        )
        raise ValueError(
            f"two models of one root type claim the same selector: {detail} — "
            "both would take the production alias and the consumer would find two matches"
        )


def card_to_metadata(card: Card) -> dict[str, object]:
    """Build the wandb-artifact metadata for a card.

    Returns exactly the selection dimensions the consumer reads plus the non-contract
    ``source_model_id`` for traceability. It deliberately omits the wandb-intrinsic keys
    (``registry_id`` / ``version`` / ``weights_checksum``), which the consumer injects
    from the artifact, and preserves ``mode`` verbatim (the space in
    ``"multiplant cylinder"`` is kept — only ``collection_id`` touches the raw id).

    Selectors are emitted as **plain JSON-native dicts**, not ``Selector`` instances:
    ``wandb.Artifact(metadata=...)`` runs the mapping through ``validate_metadata``,
    which coerces rather than rejects, degrading a pydantic model to its ``repr`` string
    and publishing unreadable metadata with a zero exit code. The four keys are spelled
    out rather than dumped, because ``Selector`` is ``extra="ignore"`` — a stray key
    would be silently dropped by the contract rather than rejected, so the exact key set
    is the producer's to keep.

    Args:
        card: The card to describe.

    Returns:
        The metadata mapping (validates against ``ModelCard``).
    """
    return {
        "root_type": card.root_type,
        "selectors": [
            {
                "species": selector.species,
                "mode": selector.mode,
                "age_min": selector.age_min,
                "age_max": selector.age_max,
            }
            for selector in card.selectors
        ],
        "source_model_id": card.source_model_id,
    }


def collection_id(card: Card) -> str:
    r"""Return the registry collection id for a card's physical model.

    Derived from ``source_model_id`` rather than from the selection tuple: a card with
    several species has no single species to name itself after. The formula is to
    replace each ``/`` and each ``=`` with ``-`` and change nothing else — both are
    illegal in a wandb artifact name (``Artifact.__init__`` enforces
    ``^[a-zA-Z0-9_\-.]+$``, and every ``source_model_id`` ends in ``n=NNN``).

    The mapping is not injective in principle — two ids differing only in ``/`` versus
    ``=`` collapse — so callers keep their duplicate-id fail-fast guard.

    Args:
        card: The card to name.

    Returns:
        A string like ``"rice-older-crown-221208_113552.multi_instance.n-574"``.
    """
    return card.source_model_id.replace("/", "-").replace("=", "-")
