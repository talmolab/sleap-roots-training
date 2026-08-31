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
import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path
from typing import Optional

import sleap_io as sio
from omegaconf import OmegaConf

from sleap_roots_training.registry.chooser import (
    ROOT_TYPE_VOCAB,
    SPECIES_VOCAB,
    parse_age_window,
)

logger = logging.getLogger(__name__)

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
        verified: Whether this row's node count has been checked against a real artifact.
            The table header has always distinguished VERIFIED from TRANSCRIBED, NOT
            VERIFIED in prose, but the loader treated every row identically, so nothing
            downstream could tell a confirmed count from a transcribed one (blocking review
            of #40). A package built against an unverified count is not wrong, but a
            corrected row later makes packages built before and after indistinguishable —
            which is what recording the table hash alongside the package prevents.
    """

    species: str
    root_type: str
    age: Optional[str]
    node_count: int
    verified: bool = False

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
            an age list is not a contiguous window, two rows describe the same
            ``(species, root_type, age)``, or a pair carries both an age-agnostic row and
            an age-split one.
    """
    # resolve=False for the same reason the selection matrix uses it: the table has no
    # interpolations, and a value containing `${...}` must not be treated as one.
    data = OmegaConf.to_container(OmegaConf.load(str(table_path)), resolve=False)
    if not isinstance(data, dict):
        raise ValueError(
            f"{table_path}: top level is a {type(data).__name__}, expected a mapping with "
            "a `skeletons:` key"
        )
    raw_rows = data.get("skeletons") or []
    if not isinstance(raw_rows, list):
        raise ValueError(
            f"{table_path}: `skeletons:` is a {type(raw_rows).__name__}, expected a list "
            "of rows"
        )
    if not raw_rows:
        raise ValueError(
            f"{table_path}: no `skeletons:` rows found (check the top-level key)"
        )

    rows: list[SkeletonRow] = []
    seen: set[tuple[str, str, Optional[str]]] = set()
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict):
            raise ValueError(
                f"row {index}: expected a mapping of keys, got a "
                f"{type(raw).__name__}"
            )
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
        verified = raw.get("verified", False)
        if not isinstance(verified, bool):
            raise ValueError(
                f"row {index}: verified must be true or false, got {verified!r}"
            )
        rows.append(
            SkeletonRow(
                species=species,
                root_type=root_type,
                age=age,
                node_count=node_count,
                verified=verified,
            )
        )

    # A pair with both an age-agnostic row and an age-split one loads cleanly under the
    # per-key dedup above — the keys differ — but `lookup_skeleton` returns the agnostic
    # row before it ever consults the age, so the age-split rows are unreachable. Both
    # `(rice, crown, null)` and `(rice, crown, "6,7,8")` could sit in the table with the
    # second silently doing nothing, which is the failure the dedup exists to prevent, one
    # level up (blocking review of #40).
    by_pair: dict[tuple[str, str], set[Optional[str]]] = {}
    for row in rows:
        by_pair.setdefault((row.species, row.root_type), set()).add(row.age)
    for (species, root_type), ages in sorted(by_pair.items(), key=lambda item: item[0]):
        if None in ages and len(ages) > 1:
            split = sorted(age for age in ages if age is not None)
            raise ValueError(
                f"{species!r}/{root_type!r} has both an age-agnostic row (age: null) and "
                f"age-split row(s) for {split}. A lookup takes the age-agnostic row "
                "without ever consulting the age, so the age-split rows would never be "
                "reached. Either split the pair completely, or drop the split rows."
            )
    return tuple(rows)


@lru_cache(maxsize=8)
def _parse_table_cached(
    table_path: Path, content_sha256: str
) -> tuple[SkeletonRow, ...]:
    """Parse a table, memoized on the file's identity *and* its exact contents.

    ``content_sha256`` is unused in the body and is there purely to key the cache: an
    edited table hashes differently and is re-parsed, so memoizing cannot serve a stale
    answer. Keying on the path alone would make an in-place edit invisible until the
    process restarted — a footgun aimed at exactly the operator correcting a node count,
    which the table's own header says is expected for three of the five crops.

    The first attempt keyed on ``(mtime_ns, size)``, which is cheaper and *wrong*: the
    realistic edit is one digit of a ``node_count``, which leaves the size identical, and
    filesystem timestamp granularity is coarser than the gap between two writes in a test
    or a script. It passed in isolation and failed in the full suite. Hashing a few KB
    costs microseconds against the ~6.5 ms parse-and-validate this avoids, so correctness
    here is close to free.

    Args:
        table_path: Path to the table YAML.
        content_sha256: The file's content hash, as the cache key.

    Returns:
        The parsed rows, in file order.
    """
    del content_sha256  # Cache key only.
    return _parse_table(table_path)


def load_skeleton_table(path: Optional[Path] = None) -> tuple[SkeletonRow, ...]:
    """Load and validate the skeleton table.

    Memoized (blocking review of #40). Every call re-read and re-validated the YAML, at a
    measured ~6.5 ms; :func:`~...build_package.skeleton_for` calls
    :func:`lookup_skeleton` once per age, and is itself called once by the builder and
    once by the orchestrator, so a 10-age two-root-type build spent roughly a quarter of a
    second re-parsing a file that cannot change mid-build. The rows are frozen dataclasses
    in a tuple, so callers cannot mutate the cached value.

    Args:
        path: Path to a table YAML; defaults to the packaged ``data/skeletons.yaml``.

    Returns:
        The parsed rows, in file order.

    Raises:
        ValueError: If the table fails validation; see :func:`_parse_table`.
    """
    if path is not None:
        return _load_fingerprinted(Path(path))
    # Read within the ``as_file`` context so a zip-imported resource stays valid.
    resource = files(_DATA_PACKAGE).joinpath(_DATA_RESOURCE)
    with as_file(resource) as resolved:
        return _load_fingerprinted(Path(resolved))


def _load_fingerprinted(table_path: Path) -> tuple[SkeletonRow, ...]:
    """Return the parsed table, re-parsing only when the file has changed.

    Args:
        table_path: Path to the table YAML.

    Returns:
        The parsed rows, in file order.

    Raises:
        FileNotFoundError: If the table does not exist.
    """
    digest = hashlib.sha256(table_path.read_bytes()).hexdigest()
    return _parse_table_cached(table_path, digest)


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


def _warn_if_unverified(row: SkeletonRow) -> SkeletonRow:
    """Log a warning when a package is about to be built against a transcribed node count.

    The table's header has always said which rows are VERIFIED and which are TRANSCRIBED,
    NOT VERIFIED, but nothing acted on it (blocking review of #40). An unverified count is
    not an error — it is the best information available, and refusing to build on it would
    make three of the five crops unlabelable — but the operator should know before handing
    a package to a labeler, because correcting the row afterwards invalidates the labels
    rather than the package.

    Args:
        row: The matched row.

    Returns:
        The same row, unchanged.
    """
    if not row.verified:
        logger.warning(
            "Skeleton for (%s, %s) is %d nodes, TRANSCRIBED BUT NOT VERIFIED against a "
            "real artifact. The package will record this table's SHA256, so it stays "
            "distinguishable if the row is corrected — but confirm the count against Bloom "
            "or existing labels before a labeler starts work.",
            row.species,
            row.root_type,
            row.node_count,
        )
    return row


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

    # At most one, and never alongside an age-split row: `_parse_table` rejects both a
    # duplicate key and a pair that mixes the two, so taking it here cannot shadow anything.
    agnostic = [row for row in candidates if row.age is None]
    if agnostic:
        return _warn_if_unverified(agnostic[0])

    windows = [(row, row.age_window) for row in candidates]
    if age is None:
        listed = ", ".join(f"{lo}-{hi} DAG" for _, (lo, hi) in windows)
        raise ValueError(
            f"({species!r}, {root_type!r}) splits by plant age ({listed}), so an age is "
            "required to choose a skeleton."
        )
    for row, (low, high) in windows:
        if low <= age <= high:
            return _warn_if_unverified(row)
    listed = ", ".join(f"{lo}-{hi} DAG" for _, (lo, hi) in windows)
    raise ValueError(
        f"({species!r}, {root_type!r}) has no skeleton for age {age} DAG; the table "
        f"covers {listed}."
    )
