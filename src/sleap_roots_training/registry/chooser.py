"""Load and validate the committed production model selection matrix.

The matrix is a committed YAML file read via OmegaConf (the repo's config idiom) into
plain, typed records. It keeps the models-downloader chooser-table schema, and its native
``age`` comma-list is parsed here to a contiguous ``(age_min, age_max)`` window.

Its rows no longer come from one source table — some were transcribed from the 20250204
``model_chooser_table.xlsx``, others set by an owner decision — so provenance is carried
in the file and enforced here: every row has a ``source``, and an ``origins`` map records
where each model's zip came from and what pinned it. A row cannot be added without
saying so.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Optional, get_args

from omegaconf import OmegaConf
from sleap_roots_contracts import Mode, RootType


def _vocab_from_contract_literal(
    alias: object, name: str, vocab_name: str
) -> frozenset[str]:
    """Derive a string vocabulary from a contract-owned ``Literal``, or refuse to import.

    Args:
        alias: The contract alias to destructure, e.g. ``sleap_roots_contracts.Mode``.
        name: Its dotted name, used in the error so the reader knows what to go look at.
        vocab_name: The constant being derived, likewise for the error.

    Returns:
        The alias's members as a frozenset of strings.

    Raises:
        RuntimeError: If ``alias`` is not a ``Literal`` of strings.
    """
    # Validate the raw tuple, and only build the frozenset once its members are known to
    # be strings. Hashing comes first otherwise, and `Annotated`'s metadata slot accepts
    # any object — `Annotated[Literal[...], {"deprecated": True}]` is legal and its dict
    # is unhashable, so `frozenset(get_args(alias))` raises `TypeError: unhashable type`
    # from *inside* this guard, naming neither the alias nor the constant. That is the
    # same class of failure as the `sorted()` one noted below: an error raised while
    # reporting an error, which buries the diagnosis.
    args = get_args(alias)
    if not args or not all(isinstance(member, str) for member in args):
        # `typing.get_args()` does not raise on a shape it cannot destructure; it
        # degrades, in two different directions, and neither one is an error until much
        # later:
        #
        #   Enum / plain str alias         -> ()                        -> empty vocabulary
        #   Annotated[Literal[...], Field] -> (Literal[...], FieldInfo)  -> typing objects
        #   Optional[Literal[...]]         -> (Literal[...], NoneType)   -> typing objects
        #   Union[Literal[...], Literal[]] -> (Literal[...], Literal[])  -> typing objects
        #
        # Only the first is empty, so an emptiness check alone misses the other three —
        # and `Annotated[..., Field(...)]` is idiomatic for a pydantic-first contracts
        # package. In all four, no real member is in the vocabulary and the
        # `frozenset[str]` annotation on the constant becomes a runtime falsehood. Left
        # to surface on its own it does so inside the *error-reporting* path (`sorted()`
        # over mixed types) and at pytest collection time, far from the cause. So fail
        # here, at the seam, naming what changed.
        #
        # Deliberately no `sorted()` on the members below: they are exactly the values
        # whose type is in question, and sorting them is what crashes while reporting.
        raise RuntimeError(
            f"{name} did not yield a vocabulary of strings via typing.get_args(); "
            f"{vocab_name} cannot be derived from it. {name.rsplit('.', 1)[-1]} is "
            f"probably no longer a plain Literal. Got: {alias!r} -> "
            f"{[repr(arg) for arg in args]}"
        )
    return frozenset(args)


#: Canonical species vocabulary the consumer selects on. Owned here, not by the
#: contract: a ``Selector``'s ``species`` is a free ``str``, so there is no
#: contract-side vocabulary to defer to. (The card itself no longer carries ``species``
#: at all — it lives one level down, on each selector.)
#:
#: Members are lowercase common names because that is exactly what the consumer
#: compares against: Bloom stores ``species.common_name`` capitalized ("Wheat"),
#: bloomctl's ``resolve_params`` lowercases it, and predict and the traits chooser then
#: match by plain string equality (verified in code for
#: talmolab/sleap-roots-training#72). A capitalized member would never match a scan.
SPECIES_VOCAB: frozenset[str] = frozenset(
    {"soybean", "canola", "pennycress", "arabidopsis", "rice", "wheat", "sorghum"}
)
#: Canonical mode vocabulary the consumer selects on, derived from the contract-owned
#: ``sleap_roots_contracts.Mode`` rather than restated here. ``ModelCard.mode`` matches
#: this vocabulary exactly (no case or whitespace normalization), so a mode this loader
#: accepts is a mode the consumer can match — by construction, not by reconciliation.
MODE_VOCAB: frozenset[str] = _vocab_from_contract_literal(
    Mode, "sleap_roots_contracts.Mode", "MODE_VOCAB"
)
#: Canonical root-type vocabulary, derived from the contract-owned
#: ``sleap_roots_contracts.RootType`` for the same reason as ``MODE_VOCAB``. It backs the
#: ``experiment.root_type`` check in ``config``, the ``root_types`` check on a labeling
#: package's metadata, and the skeleton table — all three of which previously kept their
#: own hand-written copy of these three strings.
#:
#: Membership only. ``registry/cards.py`` deliberately keeps its own ordered ``_ROOT_SLOTS``
#: rather than deriving one from this: reordering a ``Literal``'s members is a no-op for a
#: type annotation, so deriving card *emission* order from the contract would let an
#: upstream no-op silently reorder published cards. Order is a presentation decision this
#: repo owns; membership is not.
ROOT_TYPE_VOCAB: frozenset[str] = _vocab_from_contract_literal(
    RootType, "sleap_roots_contracts.RootType", "ROOT_TYPE_VOCAB"
)

_DATA_PACKAGE = "sleap_roots_training.registry"
_DATA_RESOURCE = "data/model_selection.yaml"


@dataclass(frozen=True)
class ModelOrigin:
    """Where one model's ``<model_id>.zip`` came from, and what pinned that exact file.

    Attributes:
        snapshot: The models-downloader snapshot the zip ships in (e.g. ``"20250204"``),
            or ``None`` when it ships in none (an experiment run's own models).
        location: The directory under which ``<model_id>.zip`` sits, relative to a run
            or a snapshot — never a share path.
        pinned_by: What selected that exact file (a chooser table, a run's
            ``model_paths.csv``).
    """

    snapshot: Optional[str]
    location: str
    pinned_by: str


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
        source: Why the row exists with its window (a chooser table, an owner decision).
    """

    species: str
    mode: str
    age: str
    primary_model_id: Optional[str]
    lateral_model_id: Optional[str]
    crown_model_id: Optional[str]
    source: str


@dataclass(frozen=True)
class SelectionMatrix:
    """The parsed selection matrix: rows plus per-model checksums and origins.

    Attributes:
        rows: The selection rows, in file order.
        checksums: Map of ``model_id`` to the SHA256 of its source ``.zip``.
        origins: Map of ``model_id`` to its :class:`ModelOrigin`, covering exactly the
            models the rows reference.
    """

    rows: tuple[SelectionRow, ...]
    checksums: dict[str, str]
    origins: dict[str, ModelOrigin]


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
        ValueError: If the file cannot be read, is not valid YAML, does not parse to a
            mapping, a row's ``species`` or ``mode`` is not in the canonical
            vocabulary, or the provenance (a row's ``source``, the ``origins`` map) is
            missing, mistyped, or stale. Read and parse failures are normalized to ``ValueError`` (from
            ``OSError`` / a YAML parse error) so a caller has one type to handle.
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
    # Every way the *file* can be unusable is normalized to ValueError naming the path,
    # so a caller has one exception type to wrap. `seed-registry` promises operators a
    # clean CLI error rather than a traceback for a rejected matrix, and it can only
    # deliver that against a single type -- raw, these arrive as three unrelated ones
    # that no reasonable `except` names together: IsADirectoryError/PermissionError
    # (a directory reaches here; click's `exists=True` only checks existence),
    # yaml.ParserError (a hand-edited matrix -- the likeliest of the three), and
    # AttributeError from `data.get` below when the top level parses to a sequence.
    #
    # resolve=False: the matrix has no interpolations, and a model id that happened
    # to contain a ``${...}`` sequence must not be treated as one.
    try:
        loaded = OmegaConf.load(str(matrix_path))
    except OSError as error:
        raise ValueError(
            f"{matrix_path}: cannot read the selection matrix: {error}"
        ) from error
    except Exception as error:
        # Deliberately broad, and deliberately scoped to this one call. Parsing YAML
        # fails in types this package does not depend on: PyYAML's ParserError and
        # ScannerError arrive *through* omegaconf, which neither wraps them nor makes
        # pyyaml a dependency declared here. Naming them would mean either importing an
        # undeclared package or guessing at the set, and a guess that misses re-opens
        # exactly the traceback this normalization exists to close.
        raise ValueError(f"{matrix_path}: not valid YAML: {error}") from error

    data = OmegaConf.to_container(loaded, resolve=False)
    if not isinstance(data, dict):
        raise ValueError(
            f"{matrix_path}: top level is a {type(data).__name__}, "
            "expected a mapping with a `models:` key"
        )

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
        # A model id must be a string or absent. Without this a row whose id parses to
        # a non-string scalar (an unquoted YAML number, a bool, a nested mapping) sails
        # past every other check and surfaces much later as an opaque AttributeError
        # inside `cards.collection_id`, at `--execute` time -- while every other
        # malformed-row case gets a clean, row-numbered ValueError here.
        model_ids = {
            slot: raw.get(slot)
            for slot in ("primary_model_id", "lateral_model_id", "crown_model_id")
        }
        for slot, model_id in model_ids.items():
            if model_id is not None and not isinstance(model_id, str):
                raise ValueError(
                    f"row {index}: {slot} must be a string or null, got "
                    f"{type(model_id).__name__} ({model_id!r})"
                )

        # After the vocabulary and model-id checks, so a row that is wrong in an older,
        # more specific way keeps reporting that rather than its missing provenance.
        source = raw.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(
                f"row {index}: `source` must be a non-empty string saying why the row "
                f"exists, got {source!r}"
            )

        rows.append(
            SelectionRow(
                species=species,
                mode=mode,
                age=str(raw["age"]),
                primary_model_id=model_ids["primary_model_id"],
                lateral_model_id=model_ids["lateral_model_id"],
                crown_model_id=model_ids["crown_model_id"],
                source=source,
            )
        )

    checksums = dict(data.get("checksums", {}))
    origins = _parse_origins(data.get("origins"), rows)
    return SelectionMatrix(rows=tuple(rows), checksums=checksums, origins=origins)


def _parse_origins(raw, rows: list[SelectionRow]) -> dict[str, ModelOrigin]:
    """Validate that ``origins`` covers exactly the rows' models, and parse it.

    Runs only after every row is read, so a later row's per-row error is reported before
    an earlier row's missing origin. Strict in both directions — unlike ``checksums`` —
    because an origin for a model no row references is a stale claim about provenance.
    """
    referenced: list[str] = []
    for row in rows:
        for model_id in (
            row.primary_model_id,
            row.lateral_model_id,
            row.crown_model_id,
        ):
            if model_id is not None and model_id not in referenced:
                referenced.append(model_id)

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"`origins` must be a mapping of model id to its origin, got a "
            f"{type(raw).__name__}"
        )

    origins: dict[str, ModelOrigin] = {}
    for model_id in referenced:
        if model_id not in raw:
            raise ValueError(
                f"{model_id}: no `origins` entry (where its zip came from)"
            )
        entry = raw[model_id]
        if not isinstance(entry, dict):
            raise ValueError(
                f"{model_id}: its `origins` entry must be a mapping with `snapshot`, "
                f"`location` and `pinned_by`, got {entry!r}"
            )
        for key in ("location", "pinned_by"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{model_id}: origin `{key}` must be a non-empty string, got {value!r}"
                )
        # Required, with `null` explicit: an omitted key read as None would silently
        # claim the zip ships in no snapshot.
        if "snapshot" not in entry:
            raise ValueError(
                f"{model_id}: origin has no `snapshot` key (use null if the zip ships "
                f"in no models-downloader snapshot)"
            )
        snapshot = entry["snapshot"]
        if snapshot is not None and not isinstance(snapshot, str):
            raise ValueError(
                f"{model_id}: origin `snapshot` must be a quoted string or null, got "
                f"{type(snapshot).__name__} ({snapshot!r})"
            )
        origins[model_id] = ModelOrigin(
            snapshot=snapshot, location=entry["location"], pinned_by=entry["pinned_by"]
        )

    stale = sorted(set(raw) - set(referenced))
    if stale:
        raise ValueError(f"stale `origins` for models no row references: {stale}")
    return origins
