"""The package metadata a labeling package is built against.

design.md F4: no vault script emits *structured* package metadata. The values exist — as
hand-edited English in ``generate_readme.py`` and as constants duplicated in
``build_slp_project.py`` — but nothing a consumer can parse, which is why Decision 3 calls
this new design rather than a port.

This module holds the fields the **builder** requires, so a build cannot succeed while the
package's own identity is unstated (task 4.6). Task 8.3 extends it with the rest of what
``#10``'s ``LabelCard`` needs — ``bloom_experiment_id``, the accession map, and the
selection parameters — and defines the on-disk file. Keeping the required-at-build subset
here means the check exists before the file format is settled, rather than after.
"""

from __future__ import annotations

from dataclasses import dataclass

from sleap_roots_training.registry.chooser import MODE_VOCAB, SPECIES_VOCAB

#: Root types a labeling package can be built for. Matches the contract's ``RootType``
#: literal, which is what ``#10``'s ``LabelCard`` validates against.
ROOT_TYPE_VOCAB = frozenset({"primary", "lateral", "crown"})


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
        root_types: The root types this package is for, in output order. Each one must
            yield at least one labeled frame or the build fails (task 4.4) — a package
            declaring a root type it has no labels for is an empty selection reported as
            a success.
    """

    species: str
    mode: str
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
