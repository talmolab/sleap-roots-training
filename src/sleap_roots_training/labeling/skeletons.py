"""Load and validate the committed per-crop labeling skeleton table.

design.md Decision 7. ``build_slp_project.py`` hardcoded a 6-node ``soybean_primary`` and a
4-node ``soybean_lateral`` and was edited by hand per crop, while its own command doc
advertised a ``--crop`` argument and tabulated five species. There is no parameterized
original to port, so this is ours to build — and it mirrors
``registry/data/model_selection.yaml``, which already solves the same problem: a committed,
provenance-stamped table, validated on load with row-numbered errors, hashable into run
lineage.

The table is **advisory and partly unverified**, and its header says so. A missing
``(species, root_type)`` therefore fails loudly rather than defaulting — pennycress has no
row on purpose — because a wrong node count produces a labeling package that looks fine and
cannot be combined with anything.

These are the **native** skeletons, not Tier 2.7's unified one; see the table's header.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Optional

import sleap_io as sio
from omegaconf import OmegaConf

from sleap_roots_training.labeling.metadata import ROOT_TYPE_VOCAB
from sleap_roots_training.registry.chooser import SPECIES_VOCAB, parse_age_window

_DATA_PACKAGE = "sleap_roots_training.labeling"
_DATA_RESOURCE = "data/skeletons.yaml"


@dataclass(frozen=True)
class SkeletonRow:
    """One row of the skeleton table.

    Attributes:
        species: The crop the row describes.
        root_type: The root type the row describes.
        age: The native chooser age comma-list this row applies to, or ``None`` for every
            age. Only rice splits by age.
        node_count: How many nodes a labeler places along the root.
    """

    species: str
    root_type: str
    age: Optional[str]
    node_count: int

    @property
    def age_window(self) -> Optional[tuple[int, int]]:
        """Return the ``(min, max)`` age window, or ``None`` if the row is age-agnostic."""
        return None if self.age is None else parse_age_window(self.age)

    @property
    def node_names(self) -> tuple[str, ...]:
        """Return ``("r1", ..., "rN")`` — the fixed convention, base first, tip last."""
        return tuple(f"r{i}" for i in range(1, self.node_count + 1))

    def to_skeleton(self) -> sio.Skeleton:
        """Build the ``sleap_io`` skeleton this row describes.

        Returns:
            A chain skeleton named ``"{species}_{root_type}"``, matching the names the
            vault script wrote so a new package's skeleton is recognizable as the same
            one.
        """
        names = self.node_names
        return sio.Skeleton(
            nodes=list(names),
            edges=[(names[i], names[i + 1]) for i in range(len(names) - 1)],
            name=f"{self.species}_{self.root_type}",
        )


def _parse_table(table_path: Path) -> tuple[SkeletonRow, ...]:
    """Parse and validate a skeleton table YAML, with row-numbered errors.

    Args:
        table_path: Path to the table YAML.

    Returns:
        The parsed rows, in file order.

    Raises:
        ValueError: If the file has no rows, a row is missing a required key, a species or
            root type is outside its vocabulary, a node count is not a positive integer,
            an age list is not a contiguous window, or two rows describe the same
            ``(species, root_type, age)``.
    """
    # resolve=False for the same reason the selection matrix uses it: the table has no
    # interpolations, and a value containing `${...}` must not be treated as one.
    data = OmegaConf.to_container(OmegaConf.load(str(table_path)), resolve=False)
    raw_rows = (data or {}).get("skeletons") or []
    if not raw_rows:
        raise ValueError(
            f"{table_path}: no `skeletons:` rows found (check the top-level key)"
        )

    rows: list[SkeletonRow] = []
    seen: set[tuple[str, str, Optional[str]]] = set()
    for index, raw in enumerate(raw_rows):
        for required in ("species", "root_type", "node_count"):
            if required not in raw:
                raise ValueError(f"row {index}: missing required key {required!r}")
        species, root_type = raw["species"], raw["root_type"]
        if species not in SPECIES_VOCAB:
            raise ValueError(
                f"row {index}: unknown species {species!r} "
                f"(expected one of {sorted(SPECIES_VOCAB)})"
            )
        if root_type not in ROOT_TYPE_VOCAB:
            raise ValueError(
                f"row {index}: unknown root_type {root_type!r} "
                f"(expected one of {sorted(ROOT_TYPE_VOCAB)})"
            )
        node_count = raw["node_count"]
        if not isinstance(node_count, int) or node_count < 2:
            raise ValueError(
                f"row {index}: node_count must be an integer >= 2, got {node_count!r}. "
                "A skeleton with fewer than two nodes has no edge to label along."
            )
        age = raw.get("age")
        if age is not None:
            age = str(age)
            # Raises with the same message the selection matrix uses for a gapped window.
            parse_age_window(age)
        key = (species, root_type, age)
        if key in seen:
            raise ValueError(
                f"row {index}: duplicate entry for {species!r}/{root_type!r} at age "
                f"{age!r}; a lookup would silently take the first"
            )
        seen.add(key)
        rows.append(
            SkeletonRow(
                species=species, root_type=root_type, age=age, node_count=node_count
            )
        )
    return tuple(rows)


def load_skeleton_table(path: Optional[Path] = None) -> tuple[SkeletonRow, ...]:
    """Load and validate the skeleton table.

    Args:
        path: Path to a table YAML; defaults to the packaged ``data/skeletons.yaml``.

    Returns:
        The parsed rows, in file order.

    Raises:
        ValueError: If the table fails validation; see :func:`_parse_table`.
    """
    if path is not None:
        return _parse_table(Path(path))
    # Read within the ``as_file`` context so a zip-imported resource stays valid.
    resource = files(_DATA_PACKAGE).joinpath(_DATA_RESOURCE)
    with as_file(resource) as resolved:
        return _parse_table(Path(resolved))


def skeleton_table_sha256(path: Optional[Path] = None) -> str:
    """Return the SHA256 of the skeleton table's bytes.

    Mirrors ``chooser.matrix_sha256``: it is what pins the exact table a package was built
    against when the metadata records it.

    Args:
        path: Path to a table YAML; defaults to the packaged table.

    Returns:
        The hex SHA256 of the file bytes.
    """
    if path is not None:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    resource = files(_DATA_PACKAGE).joinpath(_DATA_RESOURCE)
    with as_file(resource) as resolved:
        return hashlib.sha256(Path(resolved).read_bytes()).hexdigest()


def lookup_skeleton(
    species: str,
    root_type: str,
    age: Optional[int] = None,
    table: Optional[tuple[SkeletonRow, ...]] = None,
) -> SkeletonRow:
    """Return the skeleton row for a species and root type, failing if there is none.

    Args:
        species: The crop.
        root_type: The root type.
        age: Plant age in days. Required only where the table splits by age (rice); an
            age-agnostic row matches whatever is passed.
        table: The table to search; defaults to the packaged one.

    Returns:
        The matching row.

    Raises:
        ValueError: If no row matches, if the species has age-split rows and no age was
            given, or if the given age falls outside every window for that pair.
    """
    rows = load_skeleton_table() if table is None else table
    candidates = [
        row for row in rows if row.species == species and row.root_type == root_type
    ]
    if not candidates:
        available = sorted({(r.species, r.root_type) for r in rows})
        raise ValueError(
            f"No labeling skeleton is defined for ({species!r}, {root_type!r}). The "
            f"table covers {available}. It is transcribed from an advisory source and "
            "ships incomplete on purpose — pennycress has no row — so this fails rather "
            "than guessing a node count. Add a verified row before labeling this crop."
        )

    agnostic = [row for row in candidates if row.age is None]
    if agnostic:
        return agnostic[0]

    windows = [(row, row.age_window) for row in candidates]
    if age is None:
        listed = ", ".join(f"{lo}-{hi} DAG" for _, (lo, hi) in windows)
        raise ValueError(
            f"({species!r}, {root_type!r}) splits by plant age ({listed}), so an age is "
            "required to choose a skeleton."
        )
    for row, (low, high) in windows:
        if low <= age <= high:
            return row
    listed = ", ".join(f"{lo}-{hi} DAG" for _, (lo, hi) in windows)
    raise ValueError(
        f"({species!r}, {root_type!r}) has no skeleton for age {age} DAG; the table "
        f"covers {listed}."
    )
