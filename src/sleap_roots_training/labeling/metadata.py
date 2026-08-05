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
from typing import Mapping, Sequence

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
)

#: Root types a labeling package can be built for. Matches the contract's ``RootType``
#: literal, which is what ``#10``'s ``LabelCard`` validates against.
ROOT_TYPE_VOCAB = frozenset({"primary", "lateral", "crown"})

#: What an ``experiment`` slug may contain. It becomes part of a filename, so anything a
#: shell or a filesystem treats specially is rejected at construction rather than
#: producing a package nobody can name.
_SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


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
    """

    metadata: PackageMetadata
    bloom_experiment_id: int
    accessions: Mapping[str, str]
    selection: SelectionParameters
    frame_count: int
    skeletons: Mapping[str, Sequence[str]]
    version: str

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
        return {
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

    selection_data = _require(data, "selection")
    for key in ("seed", "plants_per_group", "views_per_plant", "total_views"):
        if key not in selection_data:
            raise ValueError(
                f"{PACKAGE_METADATA_FILENAME} is missing required key 'selection.{key}'"
            )
    return PackageRecord(
        metadata=PackageMetadata(
            species=_require(data, "species"),
            mode=_require(data, "mode"),
            experiment=_require(data, "experiment"),
            root_types=tuple(_require(data, "root_types")),
        ),
        bloom_experiment_id=int(_require(data, "bloom_experiment_id")),
        accessions=dict(_require(data, "accessions")),
        selection=SelectionParameters(
            seed=int(selection_data["seed"]),
            plants_per_group=int(selection_data["plants_per_group"]),
            views_per_plant=int(selection_data["views_per_plant"]),
            total_views=int(selection_data["total_views"]),
        ),
        frame_count=int(_require(data, "frame_count")),
        skeletons={
            rt: tuple(nodes) for rt, nodes in _require(data, "skeletons").items()
        },
        version=str(_require(data, "version")),
    )
