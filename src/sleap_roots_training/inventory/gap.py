"""Report where ``skeletons.yaml`` cannot express the corpus.

This is the headline finding, and it needs no external service. ``lookup_skeleton``
(``labeling/skeletons.py:327``) takes ``species``, ``root_type`` and ``age`` and no
``mode``, so a 6-node cylinder arabidopsis primary family and an 8-node plate one both
select the single ``(arabidopsis, primary, age: null)`` row. Node counts are read from
the files; species, mode and root type are derived from the path and are labelled as
such, because a name is not evidence.

Derivation is open, not a closed vocabulary. It recognizes the tokens the share actually
uses and returns ``None`` when it sees something else — a species the table has never
heard of is exactly what this report exists to surface, so a membership check that
rejected it would hide the finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from sleap_roots_training.inventory import discover, read
from sleap_roots_training.labeling.skeletons import SkeletonRow, load_skeleton_table

#: Marks a value read off a path rather than out of a file. Never evidence.
NAME_DERIVED = "name-derived"

#: Path tokens that name a capture mode.
_MODE_TOKENS = {
    "cyl": "cylinder",
    "cylinder": "cylinder",
    "plate": "plate",
    "plates": "plate",
}

#: Path tokens that name a root type. The team calls wheat's seminal roots **crown**, so
#: ``seminal`` and ``sr`` map to the ``crown`` row rather than becoming a ``RootType``
#: member of their own.
_ROOT_TYPE_TOKENS = {
    "primary": "primary",
    "lateral": "lateral",
    "crown": "crown",
    "seminal": "crown",
    "sr": "crown",
}

#: ``SLEAP_<species>`` is how the share names its top-level per-crop directories.
_SLEAP_DIR = re.compile(r"^SLEAP[_-](?P<species>[a-z]+)", re.IGNORECASE)

#: Species named directly in a directory or file token, e.g. ``cyl_arabidopsis_primary``.
_KNOWN_SPECIES = (
    "arabidopsis",
    "soybean",
    "canola",
    "rice",
    "pennycress",
    "wheat",
    "sorghum",
    "medicago",
    "alfalfa",
    "covercress",
)


@dataclass(frozen=True)
class Derived:
    """Species, mode and root type read off a path.

    Attributes:
        species: The crop, or ``None`` if no token named one.
        mode: The capture mode, or ``None``.
        root_type: The root type, or ``None``.
        source: Always :data:`NAME_DERIVED`. Present so an emitted row cannot carry
            these values without also carrying the fact that a name is where they
            came from.
    """

    species: Optional[str]
    mode: Optional[str]
    root_type: Optional[str]
    source: str = NAME_DERIVED


@dataclass(frozen=True)
class Observed:
    """One family paired with the facts read from its newest member.

    Attributes:
        family: The version family.
        facts: What the file said about itself.
    """

    family: discover.Family
    facts: read.FileFacts


@dataclass(frozen=True)
class ModeCollision:
    """Two or more capture modes selecting one skeleton-table row.

    Attributes:
        species: The crop both families derive.
        root_type: The root type both families derive.
        row_age: The selected row's age window, or ``None`` if age-agnostic.
        modes: The distinct capture modes that collide.
        node_counts: The distinct node counts they carry — the evidence that the single
            row cannot describe them both.
        paths: The files involved.
    """

    species: str
    root_type: str
    row_age: Optional[str]
    modes: tuple[str, ...]
    node_counts: tuple[int, ...]
    paths: tuple[str, ...]


@dataclass(frozen=True)
class UnparseableSkeleton:
    """A file whose skeleton names the existing check cannot resolve.

    Attributes:
        path: The file.
        skeleton_names: The names it carries, e.g. the auto-generated ``Skeleton-N``.
    """

    path: str
    skeleton_names: tuple[str, ...]


@dataclass
class GapReport:
    """Everywhere the skeleton table cannot describe what is on the share.

    Attributes:
        mode_collisions: Rows selected by more than one capture mode.
        uncovered_species: Derived species with no row at all.
        unparseable_skeletons: Files the ``partition("_")`` check cannot resolve.
    """

    mode_collisions: list[ModeCollision] = field(default_factory=list)
    uncovered_species: set[str] = field(default_factory=set)
    unparseable_skeletons: list[UnparseableSkeleton] = field(default_factory=list)


def _tokens(family: discover.Family) -> list[str]:
    """Return the lowercase path tokens a family's identity can be read from."""
    text = "/".join([*family.directory.parts[-3:], family.stem])
    return [t for t in re.split(r"[^A-Za-z0-9]+", text.lower()) if t]


def derive(family: discover.Family) -> Derived:
    """Read species, mode and root type off a family's path.

    Args:
        family: The family to read.

    Returns:
        The derived values, any of which may be ``None``, marked name-derived.
    """
    tokens = _tokens(family)

    species = None
    for part in family.directory.parts:
        match = _SLEAP_DIR.match(part)
        if match:
            species = match.group("species").lower()
            break
    if species is None:
        species = next((t for t in tokens if t in _KNOWN_SPECIES), None)

    mode = next((_MODE_TOKENS[t] for t in tokens if t in _MODE_TOKENS), None)
    root_type = next(
        (_ROOT_TYPE_TOKENS[t] for t in tokens if t in _ROOT_TYPE_TOKENS), None
    )
    return Derived(species=species, mode=mode, root_type=root_type)


def uncovered(
    species: Iterable[str], table: Optional[Sequence[SkeletonRow]] = None
) -> set[str]:
    """Return which of ``species`` have no row in the skeleton table.

    Args:
        species: Derived species names.
        table: The table to check; defaults to the packaged one.

    Returns:
        The species with no row.
    """
    rows = load_skeleton_table() if table is None else table
    covered = {row.species for row in rows}
    return {name for name in species if name and name not in covered}


def _is_unparseable(name: str) -> bool:
    """Whether ``skeleton.name.partition("_")`` yields a usable ``(species, root_type)``."""
    species, _, root_type = name.partition("_")
    return not species or not root_type


def build_report(
    observations: Iterable[Observed], table: Optional[Sequence[SkeletonRow]] = None
) -> GapReport:
    """Build the keying-gap report from what the scan observed.

    Args:
        observations: Families paired with their read facts.
        table: The skeleton table to check against; defaults to the packaged one.

    Returns:
        The report. Empty lists mean the table describes everything seen, which on the
        measured corpus it does not.
    """
    rows = load_skeleton_table() if table is None else table
    observations = list(observations)
    report = GapReport()

    selected: dict[tuple[str, str], list[tuple[str, int, str]]] = {}
    derived_species: set[str] = set()

    for observed in observations:
        derived = derive(observed.family)
        if derived.species:
            derived_species.add(derived.species)

        names = observed.facts.skeleton_names
        if names and any(_is_unparseable(name) for name in names):
            report.unparseable_skeletons.append(
                UnparseableSkeleton(path=str(observed.facts.path), skeleton_names=names)
            )

        node_count = observed.facts.node_count
        if derived.species and derived.root_type and derived.mode and node_count:
            key = (derived.species, derived.root_type)
            selected.setdefault(key, []).append(
                (derived.mode, node_count, str(observed.facts.path))
            )

    for (species, root_type), entries in sorted(selected.items()):
        modes = {mode for mode, _count, _path in entries}
        if len(modes) < 2:
            continue
        matching = [
            r for r in rows if r.species == species and r.root_type == root_type
        ]
        if not matching:
            # No row to collide over — that is the uncovered-species finding instead.
            continue
        report.mode_collisions.append(
            ModeCollision(
                species=species,
                root_type=root_type,
                row_age=matching[0].age,
                modes=tuple(sorted(modes)),
                node_counts=tuple(sorted({count for _m, count, _p in entries})),
                paths=tuple(sorted(path for _m, _c, path in entries)),
            )
        )

    report.uncovered_species = uncovered(derived_species, table=rows)
    return report
