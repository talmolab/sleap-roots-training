"""Load and validate the committed production model selection matrix.

The matrix is a committed, provenance-stamped YAML file mirroring the current
``models-downloader`` ``model_chooser_table.xlsx``. It is read via OmegaConf (the
repo's config idiom) into plain, typed records. The native ``age`` comma-list is
preserved in the file and parsed here to a contiguous ``(age_min, age_max)`` window,
so the file diffs row-for-row against the source xlsx and the parse is a tested step.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Optional

from omegaconf import OmegaConf

#: Canonical ``models-downloader`` species vocabulary the consumer selects on.
SPECIES_VOCAB = frozenset({"soybean", "canola", "pennycress", "arabidopsis", "rice"})
#: Canonical ``models-downloader`` mode vocabulary the consumer selects on.
MODE_VOCAB = frozenset({"cylinder", "multiplant cylinder", "plate"})

_DATA_PACKAGE = "sleap_roots_training.registry"
_DATA_RESOURCE = "data/model_selection.yaml"


@dataclass(frozen=True)
class SelectionRow:
    """One row of the selection matrix (a species/mode/age combination).

    Attributes:
        species: The species the row selects for.
        mode: The imaging mode (raw, e.g. ``"multiplant cylinder"`` with the space).
        age: The native chooser comma-list of ages (e.g. ``"2, 3, 4, 5"``).
        primary_model_id: Relative primary-root model id, or ``None`` if absent.
        lateral_model_id: Relative lateral-root model id, or ``None`` if absent.
        crown_model_id: Relative crown-root model id, or ``None`` if absent.
    """

    species: str
    mode: str
    age: str
    primary_model_id: Optional[str]
    lateral_model_id: Optional[str]
    crown_model_id: Optional[str]


@dataclass(frozen=True)
class SelectionMatrix:
    """The parsed selection matrix: rows plus per-model source checksums.

    Attributes:
        rows: The selection rows, in file order.
        checksums: Map of ``model_id`` to the SHA256 of its source ``.zip``.
    """

    rows: tuple[SelectionRow, ...]
    checksums: dict[str, str]


def parse_age_window(age: str) -> tuple[int, int]:
    """Parse a native chooser age comma-list into a contiguous window.

    Args:
        age: A comma-separated ascending list of integer ages, e.g. ``"2, 3, 4"``.

    Returns:
        A ``(age_min, age_max)`` tuple.

    Raises:
        ValueError: If the list is empty or not contiguous (has a gap).
    """
    ages = [int(part.strip()) for part in age.split(",") if part.strip()]
    if not ages:
        raise ValueError(f"empty age list: {age!r}")
    expected = list(range(ages[0], ages[-1] + 1))
    if ages != expected:
        raise ValueError(
            f"age window is not contiguous (has a gap): {age!r}; "
            f"expected {expected}, got {ages}"
        )
    return ages[0], ages[-1]


def load_selection_matrix(path: Optional[Path] = None) -> SelectionMatrix:
    """Load and validate the selection matrix from YAML.

    Args:
        path: Path to a matrix YAML; defaults to the packaged
            ``data/model_selection.yaml``.

    Returns:
        The parsed :class:`SelectionMatrix`.

    Raises:
        ValueError: If a row's ``species`` or ``mode`` is not in the canonical
            vocabulary.
    """
    if path is not None:
        return _parse_matrix(Path(path))
    # Read within the ``as_file`` context so a zip-imported resource stays valid.
    resource = files(_DATA_PACKAGE).joinpath(_DATA_RESOURCE)
    with as_file(resource) as resolved:
        return _parse_matrix(Path(resolved))


def matrix_sha256(path: Optional[Path] = None) -> str:
    """Return the SHA256 of the selection matrix file content.

    Args:
        path: Path to a matrix YAML; defaults to the packaged matrix.

    Returns:
        The hex SHA256 of the file bytes (pins the exact matrix used in lineage).
    """
    if path is not None:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    resource = files(_DATA_PACKAGE).joinpath(_DATA_RESOURCE)
    with as_file(resource) as resolved:
        return hashlib.sha256(Path(resolved).read_bytes()).hexdigest()


def _parse_matrix(matrix_path: Path) -> SelectionMatrix:
    """Parse and validate a selection matrix YAML at ``matrix_path``."""
    # resolve=False: the matrix has no interpolations, and a model id that happened
    # to contain a ``${...}`` sequence must not be treated as one.
    data = OmegaConf.to_container(OmegaConf.load(str(matrix_path)), resolve=False)

    models = data.get("models") or []
    if not models:
        raise ValueError(
            f"{matrix_path}: no `models:` rows found (check the top-level key)"
        )

    rows: list[SelectionRow] = []
    for index, raw in enumerate(models):
        for required in ("species", "mode", "age"):
            if required not in raw:
                raise ValueError(f"row {index}: missing required key {required!r}")
        species = raw["species"]
        mode = raw["mode"]
        if species not in SPECIES_VOCAB:
            raise ValueError(
                f"row {index}: unknown species {species!r} "
                f"(expected one of {sorted(SPECIES_VOCAB)})"
            )
        if mode not in MODE_VOCAB:
            raise ValueError(
                f"row {index}: unknown mode {mode!r} "
                f"(expected one of {sorted(MODE_VOCAB)})"
            )
        rows.append(
            SelectionRow(
                species=species,
                mode=mode,
                age=str(raw["age"]),
                primary_model_id=raw.get("primary_model_id"),
                lateral_model_id=raw.get("lateral_model_id"),
                crown_model_id=raw.get("crown_model_id"),
            )
        )

    checksums = dict(data.get("checksums", {}))
    return SelectionMatrix(rows=tuple(rows), checksums=checksums)
