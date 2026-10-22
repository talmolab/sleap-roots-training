"""Report where ``skeletons.yaml`` cannot express the corpus.

It needs no external service. Table rows carry a ``mode`` (add-skeleton-mode), so a
family is matched on species, mode and root type, and what the table can still fail to
express is a mode the corpus uses with no row of its own, or a node count its row does not
have. The first scan's headline finding — the table had no ``mode`` at all, so a 6-node
cylinder and an 8-node plate arabidopsis primary family selected one row — is what added
the key. Node counts are read from the files; species, mode and root type are derived from
the path and are labelled as such, because a name is not evidence.

Species is read from the filename before the folder (``Filename-First Species
Derivation``): people put other crops' data in a crop's folder to train one model. The
filename is read against :data:`KNOWN_SPECIES`, a closed vocabulary. The folder's
``SLEAP_<x>`` word is read openly, so a crop the table has never heard of still reaches
the uncovered list, where surfacing it is the point. A name that gives several species,
or several capture modes, is flagged and given none: the tool prints what it cannot
decide and stops.
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

#: The exact token for a multiplant cylinder. It reads as ``multiplant cylinder``, the
#: ``MODE_VOCAB`` spelling, and absorbs any ``cyl``/``cylinder`` token in the path. Only
#: the literal token counts: ``multi``, ``multiple`` and ``multiclass`` all occur on the
#: share meaning something else, and a labeler's name is not evidence of multiplant.
_MULTIPLANT_TOKEN = "multiplant"
_MULTIPLANT_MODE = "multiplant cylinder"

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

#: ``SLEAP_<x>`` is how the share names its top-level directories. Most name a crop, but
#: they also hold other crops' files, and some (``packages``, ``circumnutation``,
#: ``multiple``) name no crop at all.
_SLEAP_DIR = re.compile(r"^SLEAP[_-](?P<species>[a-z]+)", re.IGNORECASE)

#: Directory spellings that are a crop under another name. `SLEAP_Soy/` yields `soy`,
#: which the report then published as "not a species" while listing `soybean` separately.
_SPECIES_ALIASES = {"soy": "soybean", "arabadopsis": "arabidopsis"}

#: Crop names this program knows. A filename is read against these alone, and they sort
#: the uncovered list. A folder's ``SLEAP_<x>`` word is not filtered by them, because a
#: crop nobody has heard of is exactly the finding this report exists to surface.
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

#: A filename or folder names more than one species, so none is derived. Such a file is
#: split per species, or its per-species equivalents are found, before it is registered.
MULTI_SPECIES = "multi-species"

#: The filename names one species and the deciding folder names others, not that one.
#: The filename's species is used.
FOLDER_SPECIES_DIFFERS = "folder-species-differs"

#: The path names more than one capture mode, so none is derived.
AMBIGUOUS_MODE = "ambiguous-mode"

#: A token glued to a species, as in ``labels_ONLYpennycress``.
_ONLY_PREFIX = "only"


@dataclass(frozen=True)
class Derived:
    """Species, mode and root type read off a path.

    Attributes:
        species: The crop, or ``None`` if no part named exactly one.
        mode: The capture mode, or ``None``.
        root_type: The root type, or ``None``.
        source: Always :data:`NAME_DERIVED`. Present so an emitted row cannot carry
            these values without also carrying the fact that a name is where they
            came from.
        species_named: Every species the deciding part named, sorted.
        species_from: ``"filename"`` or ``"folder"``, whichever decided, or ``None``.
        folder_species: What the folder rule gives, sorted, whether or not it decided.
        modes_named: Every mode the path named, sorted.
        flags: What derivation could not settle, sorted.
    """

    species: Optional[str]
    mode: Optional[str]
    root_type: Optional[str]
    source: str = NAME_DERIVED
    species_named: tuple[str, ...] = ()
    species_from: Optional[str] = None
    folder_species: tuple[str, ...] = ()
    modes_named: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()


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
    return _split("/".join([*family.directory.parts, family.stem]))


def _split(text: str) -> list[str]:
    """Return the lowercase alphanumeric tokens of ``text``."""
    return [t for t in re.split(r"[^A-Za-z0-9]+", text.lower()) if t]


def _species_in(tokens: Iterable[str]) -> set[str]:
    """Return the distinct known species named by ``tokens``.

    Aliases are applied, and a leading ``only`` is stripped from a longer token. A bare
    ``only`` names nothing.
    """
    found = set()
    for token in tokens:
        if token.startswith(_ONLY_PREFIX) and len(token) > len(_ONLY_PREFIX):
            token = token[len(_ONLY_PREFIX) :]
        token = _SPECIES_ALIASES.get(token, token)
        if token in KNOWN_SPECIES:
            found.add(token)
    return found


def _folder_species(directory: Path) -> tuple[str, ...]:
    """Return the species the folder rule gives, sorted.

    The known species in the first ``SLEAP_<x>`` directory, or its open ``<x>`` where it
    names none. Where no directory is ``SLEAP_<x>``, the known species of the first
    directory that names one. Only that one directory is consulted.
    """
    for part in directory.parts:
        match = _SLEAP_DIR.match(part)
        if match:
            known = _species_in(_split(part))
            if known:
                return tuple(sorted(known))
            word = match.group("species").lower()
            return (_SPECIES_ALIASES.get(word, word),)
    for part in directory.parts:
        known = _species_in(_split(part))
        if known:
            return tuple(sorted(known))
    return ()


def _derive_species(
    family: discover.Family,
) -> tuple[Optional[str], tuple[str, ...], Optional[str], tuple[str, ...], set[str]]:
    """Return species, species named, which part decided, folder species and flags."""
    folder = _folder_species(family.directory)
    in_stem = tuple(sorted(_species_in(_split(family.stem))))
    flags: set[str] = set()
    if in_stem:
        named, decided_by = in_stem, "filename"
    elif folder:
        named, decided_by = folder, "folder"
    else:
        return None, (), None, folder, flags

    if len(named) > 1:
        flags.add(MULTI_SPECIES)
        return None, named, decided_by, folder, flags
    species = named[0]
    if (
        decided_by == "filename"
        and any(name in KNOWN_SPECIES for name in folder)
        and species not in folder
    ):
        flags.add(FOLDER_SPECIES_DIFFERS)
    return species, named, decided_by, folder, flags


def _derive_mode(tokens: list[str]) -> tuple[Optional[str], tuple[str, ...], set[str]]:
    """Return the mode, the modes named and any flag, per ``Capture Mode Derivation``."""
    named = {_MODE_TOKENS[t] for t in tokens if t in _MODE_TOKENS}
    if _MULTIPLANT_TOKEN in tokens:
        named.discard("cylinder")
        named.add(_MULTIPLANT_MODE)
    modes = tuple(sorted(named))
    if len(modes) > 1:
        return None, modes, {AMBIGUOUS_MODE}
    return (modes[0] if modes else None), modes, set()


def derive(family: discover.Family) -> Derived:
    """Read species, mode and root type off a family's path.

    Species follows ``Filename-First Species Derivation``: the stem decides, the folder
    rule is the fallback, and a deciding part naming several species gives none. Mode
    follows ``Capture Mode Derivation``: the whole path, ``multiplant`` read as
    ``multiplant cylinder``, and several distinct modes giving none. Root type is the
    first root-type token in the whole path.

    Args:
        family: The family to read.

    Returns:
        The derived values, any of which may be ``None``, marked name-derived.
    """
    tokens = _tokens(family)
    species, named, decided_by, folder, flags = _derive_species(family)
    mode, modes_named, mode_flags = _derive_mode(tokens)
    root_type = next(
        (_ROOT_TYPE_TOKENS[t] for t in tokens if t in _ROOT_TYPE_TOKENS), None
    )
    return Derived(
        species=species,
        mode=mode,
        root_type=root_type,
        species_named=named,
        species_from=decided_by,
        folder_species=folder,
        modes_named=modes_named,
        flags=tuple(sorted(flags | mode_flags)),
    )


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
        elif MULTI_SPECIES in derived.flags:
            # A pooled file is labels of each crop it names.
            derived_species.update(derived.species_named)

        names = observed.facts.skeleton_names
        if names and any(_is_unparseable(name) for name in names):
            report.unparseable_skeletons.append(
                UnparseableSkeleton(
                    path=render(observed.facts.path), skeleton_names=names
                )
            )

        node_count = observed.facts.node_count
        # A name that says too much is a different finding from one that says nothing.
        no_species = MULTI_SPECIES if MULTI_SPECIES in derived.flags else "no-species"
        no_mode = AMBIGUOUS_MODE if AMBIGUOUS_MODE in derived.flags else "no-mode"
        missing = [
            name
            for name, value in (
                (no_species, derived.species),
                ("no-root-type", derived.root_type),
                (no_mode, derived.mode),
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
