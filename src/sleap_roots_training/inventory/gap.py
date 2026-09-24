"""Report where ``skeletons.yaml`` cannot express the corpus.

It needs no external service. Table rows carry a ``mode`` (add-skeleton-mode), so a
family is matched on species, mode and root type, and what the table can still fail to
express is a mode the corpus uses with no row of its own, or a node count its row does not
have. The first scan's headline finding — the table had no ``mode`` at all, so a 6-node
cylinder and an 8-node plate arabidopsis primary family selected one row — is what added
the key. Node counts are read from the files; species, mode and root type are derived from
the path and are labelled as such, because a name is not evidence.

Derivation is open, not a closed vocabulary. It recognizes the tokens the share actually
uses and returns ``None`` when it sees something else — a species the table has never
heard of is exactly what this report exists to surface, so a membership check that
rejected it would hide the finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

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

#: Crop names this program already knows about. Used **only** to sort the uncovered
#: list for a reader — never to filter derivation, because a crop nobody has heard of
#: is exactly the finding this report exists to surface.
#: Directory spellings that are a crop under another name. `SLEAP_Soy/` yields `soy`,
#: which the report then published as "not a species" while listing `soybean` separately.
_SPECIES_ALIASES = {"soy": "soybean", "arabadopsis": "arabidopsis"}

KNOWN_SPECIES = (
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
class ModeGap:
    """A capture mode the corpus uses for a species and root type the table has no row for.

    Reported only where the table has the species and root type in some other mode: a
    species with no row at all is the uncovered-species finding instead.

    Attributes:
        species: The crop the families derive.
        root_type: The root type they derive.
        mode: The capture mode they derive, which has no row.
        table_modes: The modes the table does have for this species and root type.
        node_counts: The distinct node counts the families carry.
        paths: The files involved.
    """

    species: str
    root_type: str
    mode: str
    table_modes: tuple[str, ...]
    node_counts: tuple[int, ...]
    paths: tuple[str, ...]


@dataclass(frozen=True)
class NodeCountDisagreement:
    """Families whose node count none of their matched rows has.

    Printed, not resolved: the tool cannot tell an abandoned draft from a second
    skeleton, so it names the counts and the files and leaves the decision to a person.
    Age is not considered, because it is not derivable from a path.

    Attributes:
        species: The crop the families derive.
        mode: The capture mode they derive.
        root_type: The root type they derive.
        row_node_counts: The node counts of the table's rows for this key.
        observed: The observed node counts outside ``row_node_counts``.
        paths: The disagreeing files.
    """

    species: str
    mode: str
    root_type: str
    row_node_counts: tuple[int, ...]
    observed: tuple[int, ...]
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
        mode_gaps: Observed modes with no row of their own.
        node_count_disagreements: Observed node counts their matched rows lack.
        uncovered_species: Derived species with no row at all.
        unparseable_skeletons: Files the ``partition("_")`` check cannot resolve.
    """

    mode_gaps: list[ModeGap] = field(default_factory=list)
    node_count_disagreements: list[NodeCountDisagreement] = field(default_factory=list)
    uncovered_species: set[str] = field(default_factory=set)
    unparseable_skeletons: list[UnparseableSkeleton] = field(default_factory=list)
    families_considered: int = 0
    families_analysed: int = 0
    families_skipped_reasons: dict[str, int] = field(default_factory=dict)


def _tokens(family: discover.Family) -> list[str]:
    """Return the lowercase path tokens a family's identity can be read from.

    The **whole** path, not a window on it. Reading only the last three directories for
    mode while species read everything meant a `plates` token further up was invisible:
    on the measured corpus that hid four plate families outright and undercounted the
    8-node ones as 11 rather than 15.
    """
    text = "/".join([*family.directory.parts, family.stem])
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
        species = next((t for t in tokens if t in KNOWN_SPECIES), None)
    species = _SPECIES_ALIASES.get(species, species)

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
    observations: Iterable[Observed],
    table: Optional[Sequence[SkeletonRow]] = None,
    emit_path: Optional[Callable[[Path], str]] = None,
) -> GapReport:
    """Build the skeleton-table gap report from what the scan observed.

    Args:
        observations: Families paired with their read facts.
        table: The skeleton table to check against; defaults to the packaged one.
        emit_path: Renders a candidate path into its emitted form. Defaults to the
            filename, so a report built without it still cannot carry a directory
            chain — this is the one renderer that previously bypassed redaction.

    Returns:
        The report. Empty lists mean the table describes everything seen, which on the
        measured corpus it does not.
    """
    rows = load_skeleton_table() if table is None else table
    observations = list(observations)
    render = emit_path or (lambda path: Path(path).name)
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
                UnparseableSkeleton(
                    path=render(observed.facts.path), skeleton_names=names
                )
            )

        node_count = observed.facts.node_count
        missing = [
            name
            for name, value in (
                ("no-species", derived.species),
                ("no-root-type", derived.root_type),
                ("no-mode", derived.mode),
                ("no-node-count", None if node_count is None else True),
            )
            if not value
        ]
        if missing:
            # Recorded, not silently dropped. Without a denominator a reader cannot tell
            # the first scan's headline finding rested on 47 of 1,250 families.
            for name in missing:
                report.families_skipped_reasons[name] = (
                    report.families_skipped_reasons.get(name, 0) + 1
                )
            continue
        report.families_analysed += 1
        key = (derived.species, derived.root_type)
        selected.setdefault(key, []).append(
            (derived.mode, node_count, render(observed.facts.path))
        )

    for (species, root_type), entries in sorted(selected.items()):
        pair_rows = [
            r for r in rows if r.species == species and r.root_type == root_type
        ]
        if not pair_rows:
            # No row in any mode. An uncovered species is its own finding; a covered
            # species missing this root type is reported as neither (the spec says so).
            continue
        table_modes = tuple(sorted({r.mode for r in pair_rows}))
        by_mode: dict[str, list[tuple[int, str]]] = {}
        for mode, node_count, path in entries:
            by_mode.setdefault(mode, []).append((node_count, path))
        for mode, found in sorted(by_mode.items()):
            mode_rows = [r for r in pair_rows if r.mode == mode]
            if not mode_rows:
                report.mode_gaps.append(
                    ModeGap(
                        species=species,
                        root_type=root_type,
                        mode=mode,
                        table_modes=table_modes,
                        node_counts=tuple(sorted({count for count, _ in found})),
                        paths=tuple(sorted(path for _, path in found)),
                    )
                )
                continue
            row_counts = tuple(sorted({r.node_count for r in mode_rows}))
            off = [(count, path) for count, path in found if count not in row_counts]
            if off:
                report.node_count_disagreements.append(
                    NodeCountDisagreement(
                        species=species,
                        mode=mode,
                        root_type=root_type,
                        row_node_counts=row_counts,
                        observed=tuple(sorted({count for count, _ in off})),
                        paths=tuple(sorted(path for _, path in off)),
                    )
                )

    report.families_considered = len(observations)
    report.uncovered_species = uncovered(derived_species, table=rows)
    return report
