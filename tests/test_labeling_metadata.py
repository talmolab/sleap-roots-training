"""Tests for the package metadata the builder requires (task 4.6).

New design, not a port: design.md F4 records that no vault script emits structured package
metadata at all. Every rejection here asserts the error names the offending field, because
the failure this guards against is a package whose species, capture mode, and root types
are recoverable only by opening its ``.slp``.
"""

from __future__ import annotations

import pytest

from sleap_roots_training.labeling.metadata import PackageMetadata


def metadata(**overrides) -> PackageMetadata:
    """Build valid metadata, stating only the deviation under test."""
    fields = {
        "species": "soybean",
        "mode": "cylinder",
        "experiment": "weep",
        "root_types": ("primary", "lateral"),
    }
    fields.update(overrides)
    return PackageMetadata(**fields)


def test_valid_metadata_round_trips():
    meta = metadata()

    assert (meta.species, meta.mode, meta.root_types) == (
        "soybean",
        "cylinder",
        ("primary", "lateral"),
    )


@pytest.mark.parametrize("field", ["species", "mode", "experiment", "root_types"])
def test_an_empty_required_field_is_named(field):
    empty = () if field == "root_types" else ""

    with pytest.raises(ValueError, match=field):
        metadata(**{field: empty})


def test_an_unknown_species_is_rejected_against_the_repo_vocabulary():
    """The same ``SPECIES_VOCAB`` the training config validates against, not a new one."""
    with pytest.raises(ValueError, match="species"):
        metadata(species="wheat")


def test_an_unknown_capture_mode_is_rejected():
    with pytest.raises(ValueError, match="mode"):
        metadata(mode="lightsheet")


def test_an_unknown_root_type_is_rejected():
    with pytest.raises(ValueError, match="root_types"):
        metadata(root_types=("primary", "taproot"))


def test_a_repeated_root_type_is_rejected():
    """Two projects would claim one output filename, and the second would win silently."""
    with pytest.raises(ValueError, match="repeats"):
        metadata(root_types=("primary", "primary"))


def test_crown_is_in_the_vocabulary():
    """Rice packages are crown-only past 6 DAG, per ``model_selection.yaml``."""
    assert metadata(species="rice", root_types=("crown",)).root_types == ("crown",)


def test_metadata_is_frozen():
    """A build must not be able to change the identity it validated."""
    meta = metadata()

    with pytest.raises(Exception):
        meta.species = "rice"
