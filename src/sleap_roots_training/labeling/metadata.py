"""The package metadata a labeling package is built against.

design.md F4: no vault script emits *structured* package metadata. The values exist — as
hand-edited English in ``generate_readme.py`` and as constants duplicated in
``build_slp_project.py`` — but nothing a consumer can parse, which is why Decision 3 calls
this new design rather than a port.

:class:`PackageMetadata` holds the fields the **builder** requires, so a build cannot
succeed while the package's own identity is unstated (task 4.6). :class:`PackageRecord`
wraps it with the rest of what ``#10``'s ``LabelCard`` needs — ``bloom_experiment_id``, the
accession map, the skeletons, and the selection parameters — and is what
:data:`PACKAGE_METADATA_FILENAME` holds on disk (task 8.3). The two are separate because
the builder's requirement is narrower: it must fail on an unstated species long before a
package is assembled, and making it depend on a frame count it has not computed yet would
invert that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from omegaconf import OmegaConf

from sleap_roots_training.registry.chooser import MODE_VOCAB, SPECIES_VOCAB

#: The package metadata file's name inside a labeling package. Decision 3 makes the package
#: directory a named contract, so the filename is part of it: ``#10``'s ``publish-labels``
#: looks for exactly this.
PACKAGE_METADATA_FILENAME = "package_metadata.yaml"

_HEADER = (
    "# Package metadata for a sleap-roots labeling package.\n"
    "#\n"
    "# Written by `sleap-roots-training labeling build`. This is the parseable record of\n"
    "# what the package holds and how it was selected -- the values that previously\n"
    "# existed only as prose in a README and as constants in a build script, in two\n"
    "# hand-synced copies. `publish-labels` reads it to build a LabelCard.\n"
    "#\n"
    "# The selection block is what makes the package re-derivable: the manifest records\n"
    "# which frames were chosen, and only this records the parameters that chose them.\n"
    "# The provenance block records what they were chosen *from* -- the parameters are\n"
    "# only reproducible against the same inputs, and new waves land between re-runs.\n"
)

#: Root types a labeling package can be built for. Matches the contract's ``RootType``
#: literal, which is what ``#10``'s ``LabelCard`` validates against.
ROOT_TYPE_VOCAB = frozenset({"primary", "lateral", "crown"})

#: What an ``experiment`` slug may contain. It becomes part of a filename, so anything a
#: shell or a filesystem treats specially is rejected at construction rather than
#: producing a package nobody can name.
_SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")

#: A hex SHA256, which is what every provenance field holds.
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class PackageMetadata:
    """Identity of the labeling package being built.

    Every field is required. A build that does not state its species, capture mode, and
    root types produces a package whose skeleton and node counts are recoverable only by
    opening the ``.slp`` — the state ``docs/roadmap.md:201`` records as the reason node
    counts are unknown across the eight published collections.

    Attributes:
        species: Crop, from the repo's ``SPECIES_VOCAB``.
        mode: Capture mode, from the repo's ``MODE_VOCAB``.
        experiment: Short slug naming the experiment the package is drawn from (for
            example ``"weep"``). It goes into the ``.slp`` filenames, per the command
            doc's ``<crop>_<experiment>_<root_type>_labels.<version>.slp``, so it is
            restricted to characters that survive a filename unchanged.
        root_types: The root types this package is for, in output order. Each one must
            yield at least one labeled frame or the build fails (task 4.4) — a package
            declaring a root type it has no labels for is an empty selection reported as
            a success.
    """

    species: str
    mode: str
    experiment: str
    root_types: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate every field, naming the offending one.

        Raises:
            ValueError: If a required field is empty or outside its vocabulary.
        """
        if not self.species:
            raise ValueError("package metadata is missing required field 'species'")
        if self.species not in SPECIES_VOCAB:
            raise ValueError(
                f"package metadata field 'species' is {self.species!r}, expected one of "
                f"{sorted(SPECIES_VOCAB)}"
            )
        if not self.mode:
            raise ValueError(
                "package metadata is missing required field 'mode' (capture mode)"
            )
        if self.mode not in MODE_VOCAB:
            raise ValueError(
                f"package metadata field 'mode' is {self.mode!r}, expected one of "
                f"{sorted(MODE_VOCAB)}"
            )
        if not self.experiment:
            raise ValueError("package metadata is missing required field 'experiment'")
        if not _SLUG.fullmatch(self.experiment):
            raise ValueError(
                f"package metadata field 'experiment' is {self.experiment!r}; it names "
                "the output files, so it must be lowercase alphanumerics separated by "
                "'-' or '_'"
            )
        if not self.root_types:
            raise ValueError("package metadata is missing required field 'root_types'")
        unknown = [rt for rt in self.root_types if rt not in ROOT_TYPE_VOCAB]
        if unknown:
            raise ValueError(
                f"package metadata field 'root_types' has unknown value(s) {unknown}, "
                f"expected values from {sorted(ROOT_TYPE_VOCAB)}"
            )
        if len(set(self.root_types)) != len(self.root_types):
            raise ValueError(
                f"package metadata field 'root_types' repeats a value: {self.root_types}"
            )


@dataclass(frozen=True)
class SelectionParameters:
    """The parameters that determined which frames the package holds.

    Obligation from task 2.5. Selection is deterministic (Decision 5), but
    ``MANIFEST_COLUMNS`` records *which* frames were chosen and none of *what chose them*.
    Without these in the artifact, "recoverable from the package alone" is false, and
    Decision 6's re-derive-and-widen path is unavailable to anyone who does not still have
    the command line they ran — you cannot widen a selection whose seed you do not know.

    Attributes:
        seed: The selection seed.
        plants_per_group: Plants drawn per age x accession group.
        views_per_plant: Rotational views kept per plant.
        total_views: Rotational views the source scans hold. Recorded because it is an
            *assumption* about the capture, not a choice — a package selected against the
            wrong value holds the wrong angles (design.md F4).
    """

    seed: int
    plants_per_group: int
    views_per_plant: int
    total_views: int

    def __post_init__(self) -> None:
        """Validate the parameters, naming the offending one.

        Raises:
            ValueError: If a count is not positive, or if more views were requested per
                plant than the rotation holds.
        """
        for field in ("plants_per_group", "views_per_plant", "total_views"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(
                    f"selection parameter {field!r} is {value!r}; it counts things, so it "
                    "must be a positive integer"
                )
        if self.views_per_plant > self.total_views:
            raise ValueError(
                f"selection parameter 'views_per_plant' is {self.views_per_plant}, more "
                f"than the {self.total_views} views a scan holds"
            )


@dataclass(frozen=True)
class Provenance:
    """What a package was derived *from*, as opposed to what chose the frames.

    New in the blocking review of #40. :class:`SelectionParameters` records the parameters,
    which makes a package re-derivable only against a byte-identical pool — and the usual
    reason to re-derive one months later is that new waves have landed. The prefix-of-a-
    stable-order rule is not stable under a changed pool: ten plants at
    ``plants_per_group=3`` and seed 42 give ``['P00', 'P08', 'P09']``, and adding five more
    plants gives ``['P08', 'P09', 'P10']`` — not a superset. Monotonicity holds against the
    same pool, and nothing in the artifact let you check you had the same pool.

    ``registry/lineage`` already does git-SHA and tool-version stamping for models; this is
    the labeling-package equivalent, kept to content hashes so it stays checkable without
    the source machine.

    Attributes:
        scans_csv_sha256: SHA256 of the ``scans.csv`` the selection drew from.
        manifest_sha256: SHA256 of the ``sample_manifest.csv`` the package was built from.
            Pins the exact selection, and lets a consumer confirm the copy inside the
            package is the one the ``.slp`` files were built against.

            **The QC-cleaned pool is not recorded**, and it is the input that decides which
            plants were *eligible* to be sampled — a re-run of ``sleap-roots-analyze`` with
            different thresholds changes eligibility without touching ``scans.csv``. The
            build stage never receives ``--cleaned-csv`` (only ``select`` does), so there
            is nothing here to hash; closing that gap means threading the pool identity
            from selection into the manifest or into the build. Recorded as a known gap
            rather than papered over: this field was briefly named ``cleaned_csv_sha256``
            while holding the manifest's hash, which is worse than an absent field because
            a consumer checking their own QC table against it would get a guaranteed
            mismatch and conclude they had the wrong pool.
        skeleton_table_sha256: SHA256 of the committed skeleton table. The table is
            advisory and partly unverified, and its own header says so, so when a row is
            corrected this is what keeps packages built before and after distinguishable
            rather than silently different.
        code_version: The version or git SHA of the code that built the package.
        prediction_models: The model identifiers whose predictions seeded the ``v000``
            starting points, sorted and distinct. Labelers anchor on those starting
            points — the README calls them that — so the predicting model is a
            confounder in the ground truth that comes back, and two packages built from
            different models were previously indistinguishable in the artifact. Empty
            when the package predates this field or no prediction file was matched.
    """

    scans_csv_sha256: str
    manifest_sha256: str
    skeleton_table_sha256: str
    code_version: str
    prediction_models: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the hashes, naming the offending one.

        Raises:
            ValueError: If a hash is not 64 hex characters, or the code version is empty.
        """
        for field in (
            "scans_csv_sha256",
            "manifest_sha256",
            "skeleton_table_sha256",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise ValueError(
                    f"provenance field {field!r} is {value!r}; it must be a 64-character "
                    "hex SHA256"
                )
        if not self.code_version:
            raise ValueError("provenance is missing required field 'code_version'")


@dataclass(frozen=True)
class PackageRecord:
    """Everything about a built package that is not in the manifest or the ``.slp``.

    New design, not a port (design.md F4/F7). ``generate_readme.py`` held these values as
    English prose and ``build_slp_project.py`` held some of them again as constants, so
    they were two hand-synced copies and neither was parseable. This is the one copy, and
    :mod:`sleap_roots_training.labeling.render_readme` renders the prose *from* it rather
    than beside it.

    Attributes:
        metadata: The package identity the builder validated.
        bloom_experiment_id: The Bloom experiment the scans came from. The trace back to
            source data that ``#10``'s ``LabelCard`` needs; it lives today only inside a
            README sentence (``generate_readme.py:66``).
        accessions: Map of ``accession_id`` to accession name, as strings. Hand-maintained
            in ``generate_readme.py:85-89`` today, and looked up from Bloom by a human
            (design.md F2), so it has to be recorded where it is used.
        selection: The parameters that chose the frames.
        frame_count: Labeled frames in the package. Declared, so validation can disagree
            with the manifest rather than trusting it.
        skeletons: Node names per root type, as written into the ``.slp``. Recorded so a
            consumer knows the node count without opening the file — the state
            ``docs/roadmap.md:201`` records for the eight published collections.
        version: The package version string (``v000`` is predictions, per the labeling
            convention the README documents).
        provenance: What the package was derived from — the input hashes, the skeleton
            table hash, and the code version. Optional so a package written before the
            blocking review of #40 still reads back; absent means "not recorded", which is
            exactly the state that made those packages un-re-derivable.
    """

    metadata: PackageMetadata
    bloom_experiment_id: int
    accessions: Mapping[str, str]
    selection: SelectionParameters
    frame_count: int
    skeletons: Mapping[str, Sequence[str]]
    version: str
    provenance: Optional[Provenance] = None

    def __post_init__(self) -> None:
        """Validate the record, naming the offending field.

        Raises:
            ValueError: If the frame count is not positive, if the version is empty, or if
                the skeletons do not describe exactly the declared root types.
        """
        if (
            not isinstance(self.frame_count, int)
            or isinstance(self.frame_count, bool)
            or self.frame_count < 1
        ):
            raise ValueError(
                f"package metadata field 'frame_count' is {self.frame_count!r}; a package "
                "with no labeled frames is an empty selection reported as a success"
            )
        if not self.version:
            raise ValueError("package metadata is missing required field 'version'")
        declared = set(self.metadata.root_types)
        described = set(self.skeletons)
        undescribed = sorted(declared - described)
        if undescribed:
            raise ValueError(
                f"package metadata field 'skeletons' has no entry for root type(s) "
                f"{undescribed}. The node count is what a consumer cannot recover without "
                "opening the .slp, so a declared root type must describe its skeleton."
            )
        extra = sorted(described - declared)
        if extra:
            raise ValueError(
                f"package metadata field 'skeletons' describes root type(s) {extra} the "
                f"package does not declare (root_types={list(self.metadata.root_types)})"
            )
        # Normalize on the way in, so equality and the manifest join both hold regardless
        # of whether the caller's ids came from a CSV (ints) or from a JSON map (strings).
        object.__setattr__(
            self, "accessions", {str(k): str(v) for k, v in self.accessions.items()}
        )
        object.__setattr__(
            self,
            "skeletons",
            {rt: tuple(nodes) for rt, nodes in self.skeletons.items()},
        )

    def to_container(self) -> dict:
        """Return the record as plain data, in the order the file is written."""
        container = {
            "species": self.metadata.species,
            "mode": self.metadata.mode,
            "experiment": self.metadata.experiment,
            "root_types": list(self.metadata.root_types),
            "version": self.version,
            "bloom_experiment_id": self.bloom_experiment_id,
            "frame_count": self.frame_count,
            "accessions": dict(self.accessions),
            "selection": {
                "seed": self.selection.seed,
                "plants_per_group": self.selection.plants_per_group,
                "views_per_plant": self.selection.views_per_plant,
                "total_views": self.selection.total_views,
            },
            "skeletons": {rt: list(nodes) for rt, nodes in self.skeletons.items()},
        }
        if self.provenance is not None:
            container["provenance"] = {
                "scans_csv_sha256": self.provenance.scans_csv_sha256,
                "manifest_sha256": self.provenance.manifest_sha256,
                "skeleton_table_sha256": self.provenance.skeleton_table_sha256,
                "code_version": self.provenance.code_version,
                "prediction_models": list(self.provenance.prediction_models),
            }
        return container


def write_package_metadata(record: PackageRecord, package_dir: Path) -> Path:
    """Write the package metadata file into a package directory.

    Args:
        record: The record to write.
        package_dir: The package directory. Created if absent.

    Returns:
        The path written.
    """
    package_dir = Path(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    path = package_dir / PACKAGE_METADATA_FILENAME
    body = OmegaConf.to_yaml(OmegaConf.create(record.to_container()))
    path.write_text(_HEADER + body, encoding="utf-8")
    return path


def _require(data: dict, key: str) -> object:
    """Return ``data[key]``, failing with a message that names the missing key."""
    if key not in data or data[key] is None:
        raise ValueError(
            f"{PACKAGE_METADATA_FILENAME} is missing required key {key!r}. A package "
            "whose metadata is incomplete cannot be published: the card built from it "
            "would state less than the package holds."
        )
    return data[key]


def _require_typed(data: dict, key: str, expected: type, described: str) -> object:
    """Return ``data[key]``, failing if it is present but the wrong shape.

    Deviation (blocking review of #40). ``_require`` only checked presence, so a
    wrong-typed value was passed straight through to whatever consumed it and failed
    somewhere unhelpful: ``root_types: "primary"`` was a string, which ``tuple()`` happily
    exploded into ``('p', 'r', 'i', ...)`` before the vocabulary check rejected the letters
    one by one; ``selection: 5`` raised ``TypeError`` from an ``in`` test; ``skeletons: []``
    raised ``AttributeError`` from ``.items()``. None of ``TypeError`` or
    ``AttributeError`` is caught by the CLI, so those two reached the operator as
    tracebacks.

    Args:
        data: The parsed metadata mapping.
        key: The key to read.
        expected: The type the value must be.
        described: How to describe the expected shape in the error.

    Returns:
        The value.

    Raises:
        ValueError: If the key is absent, null, or not of the expected type.
    """
    value = _require(data, key)
    if not isinstance(value, expected):
        raise ValueError(
            f"{PACKAGE_METADATA_FILENAME} key {key!r} is a {type(value).__name__} "
            f"({value!r}), expected {described}."
        )
    return value


def _read_provenance(data: dict) -> Optional[Provenance]:
    """Return the provenance block, or ``None`` when the package predates it.

    Args:
        data: The parsed metadata mapping.

    Returns:
        The parsed provenance, or ``None`` if the key is absent.

    Raises:
        ValueError: If the block is present but malformed.
    """
    if data.get("provenance") is None:
        return None
    block = _require_typed(data, "provenance", dict, "a mapping")
    fields = (
        "scans_csv_sha256",
        "manifest_sha256",
        "skeleton_table_sha256",
        "code_version",
    )
    absent = [field for field in fields if field not in block]
    if absent:
        raise ValueError(
            f"{PACKAGE_METADATA_FILENAME} provenance block is missing "
            f"{', '.join(absent)}. A partial provenance record is worse than none: it "
            "reads as though the package can be checked against its inputs when it cannot."
        )
    return Provenance(
        **{field: str(block[field]) for field in fields},
        # Absent on a package written before this field existed, which is not an error
        # — it means the predicting model was not recorded, which is the state this
        # field exists to end.
        prediction_models=tuple(str(m) for m in block.get("prediction_models") or ()),
    )


def read_package_metadata(package_dir: Path) -> PackageRecord:
    """Read and validate the package metadata file from a package directory.

    Args:
        package_dir: The package directory.

    Returns:
        The parsed record.

    Raises:
        FileNotFoundError: If the metadata file is absent, naming it.
        ValueError: If a required key is missing, or a value is invalid.
    """
    path = Path(package_dir) / PACKAGE_METADATA_FILENAME
    if not path.is_file():
        raise FileNotFoundError(
            f"{package_dir} has no {PACKAGE_METADATA_FILENAME}. Decision 3 makes it part "
            "of the package layout, so a directory without one is not a labeling package."
        )
    data = OmegaConf.to_container(OmegaConf.load(str(path)), resolve=False)
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: top level is a {type(data).__name__}, expected a mapping"
        )

    selection_data = _require_typed(data, "selection", dict, "a mapping")
    for key in ("seed", "plants_per_group", "views_per_plant", "total_views"):
        if key not in selection_data:
            raise ValueError(
                f"{PACKAGE_METADATA_FILENAME} is missing required key 'selection.{key}'"
            )
    skeletons = _require_typed(
        data, "skeletons", dict, "a mapping of root type to nodes"
    )
    try:
        return PackageRecord(
            metadata=PackageMetadata(
                species=_require(data, "species"),
                mode=_require(data, "mode"),
                experiment=_require(data, "experiment"),
                root_types=tuple(
                    _require_typed(data, "root_types", list, "a list of root types")
                ),
            ),
            bloom_experiment_id=int(_require(data, "bloom_experiment_id")),
            accessions=dict(_require_typed(data, "accessions", dict, "a mapping")),
            selection=SelectionParameters(
                seed=int(selection_data["seed"]),
                plants_per_group=int(selection_data["plants_per_group"]),
                views_per_plant=int(selection_data["views_per_plant"]),
                total_views=int(selection_data["total_views"]),
            ),
            frame_count=int(_require(data, "frame_count")),
            skeletons={rt: tuple(nodes) for rt, nodes in skeletons.items()},
            version=str(_require(data, "version")),
            provenance=_read_provenance(data),
        )
    except (TypeError, AttributeError) as error:
        # A value of the right container type but the wrong contents — `frame_count: "six"`,
        # a node list holding a mapping. Re-raised as ValueError so it reaches the operator
        # as a message rather than as a traceback past the CLI's catch.
        raise ValueError(
            f"{PACKAGE_METADATA_FILENAME} holds a value of the wrong type: {error}"
        ) from error
