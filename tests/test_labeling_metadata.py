"""Tests for the package metadata the builder requires (task 4.6).

New design, not a port: design.md F4 records that no vault script emits structured package
metadata at all. Every rejection here asserts the error names the offending field, because
the failure this guards against is a package whose species, capture mode, and root types
are recoverable only by opening its ``.slp``.
"""

from __future__ import annotations

import pytest

from sleap_roots_training.labeling.metadata import (
    PACKAGE_METADATA_FILENAME,
    PackageMetadata,
    PackageRecord,
    SelectionParameters,
    read_package_metadata,
    write_package_metadata,
)


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


# --------------------------------------------------------------------------------------
# Task 8.3: the on-disk package metadata file.
#
# New design, not a port (F4). The values exist today in two hand-synced places —
# ``generate_readme.py``'s prose and ``build_slp_project.py``'s constants (F7) — and in
# neither of them can a consumer parse them. This file is what makes it one copy, and it is
# what #10's ``LabelCard`` reads.
# --------------------------------------------------------------------------------------


def selection(**overrides) -> SelectionParameters:
    """Build valid selection parameters, stating only the deviation under test."""
    fields = {
        "seed": 42,
        "plants_per_group": 5,
        "views_per_plant": 3,
        "total_views": 72,
    }
    fields.update(overrides)
    return SelectionParameters(**fields)


def record(**overrides) -> PackageRecord:
    """Build a valid package record, stating only the deviation under test."""
    fields = {
        "metadata": metadata(),
        "bloom_experiment_id": 10102496,
        "accessions": {"12742739": "A3244", "12742740": "WEEP-1-4"},
        "selection": selection(),
        "frame_count": 45,
        "skeletons": {
            "primary": ("r1", "r2", "r3", "r4", "r5", "r6"),
            "lateral": ("r1", "r2", "r3", "r4"),
        },
        "version": "v000",
    }
    fields.update(overrides)
    return PackageRecord(**fields)


def test_the_record_round_trips_through_the_file(tmp_path):
    """The artifact has to be readable by a consumer that never saw the build."""
    written = write_package_metadata(record(), tmp_path)

    assert written == tmp_path / PACKAGE_METADATA_FILENAME
    assert read_package_metadata(tmp_path) == record()


@pytest.mark.parametrize(
    "parameter", ["seed", "plants_per_group", "views_per_plant", "total_views"]
)
def test_every_selection_parameter_survives_into_the_file(tmp_path, parameter):
    """Obligation from task 2.5.

    Selection is deterministic, but ``MANIFEST_COLUMNS`` carries none of the parameters
    that determined it. Without them in the artifact, Decision 5's "recoverable from the
    package alone" is false and Decision 6's re-derive path cannot be followed — you
    cannot widen a selection whose seed you do not have.
    """
    write_package_metadata(record(selection=selection(**{parameter: 7})), tmp_path)

    reloaded = read_package_metadata(tmp_path)

    assert getattr(reloaded.selection, parameter) == 7


def test_reading_a_directory_without_the_file_names_it(tmp_path):
    with pytest.raises(FileNotFoundError, match=PACKAGE_METADATA_FILENAME):
        read_package_metadata(tmp_path)


@pytest.mark.parametrize(
    "key",
    [
        "species",
        "mode",
        "experiment",
        "root_types",
        "bloom_experiment_id",
        "accessions",
        "selection",
        "frame_count",
        "skeletons",
        "version",
    ],
)
def test_a_missing_key_is_named_on_read(tmp_path, key):
    """A hand-edited or older-tool package fails naming what it lacks, not with a KeyError."""
    from omegaconf import OmegaConf

    path = write_package_metadata(record(), tmp_path)
    data = OmegaConf.to_container(OmegaConf.load(str(path)))
    data.pop(key)
    OmegaConf.save(OmegaConf.create(data), str(path))

    with pytest.raises(ValueError, match=key):
        read_package_metadata(tmp_path)


def test_a_skeleton_is_required_for_every_declared_root_type():
    """The record's whole job is that node counts are recoverable without opening the .slp.

    ``docs/roadmap.md:201`` records that they are unknown across the eight published
    collections precisely because nothing wrote them down.
    """
    with pytest.raises(ValueError, match="lateral"):
        record(skeletons={"primary": ("r1", "r2", "r3", "r4", "r5", "r6")})


def test_a_skeleton_for_an_undeclared_root_type_is_rejected():
    with pytest.raises(ValueError, match="crown"):
        record(
            skeletons={
                "primary": ("r1", "r2", "r3", "r4", "r5", "r6"),
                "lateral": ("r1", "r2", "r3", "r4"),
                "crown": ("r1", "r2", "r3", "r4", "r5", "r6"),
            }
        )


def test_views_per_plant_cannot_exceed_the_rotation():
    """The same rule selection enforces (2.5), restated where the artifact records it."""
    with pytest.raises(ValueError, match="views_per_plant"):
        selection(views_per_plant=80, total_views=72)


@pytest.mark.parametrize(
    "parameter", ["plants_per_group", "views_per_plant", "total_views"]
)
def test_a_non_positive_selection_parameter_is_named(parameter):
    with pytest.raises(ValueError, match=parameter):
        selection(**{parameter: 0})


def test_a_negative_frame_count_is_rejected():
    with pytest.raises(ValueError, match="frame_count"):
        record(frame_count=-1)


def test_a_zero_frame_count_is_rejected():
    """An empty package is the F1 failure this change exists to make impossible."""
    with pytest.raises(ValueError, match="frame_count"):
        record(frame_count=0)


def test_accession_ids_are_recorded_as_strings(tmp_path):
    """They arrive from a CSV as ints and go into the manifest as strings.

    A record keyed by ``12742739`` and a manifest carrying ``"12742739"`` would not join,
    which is exactly the lookup #10's ``LabelCard`` needs.
    """
    write_package_metadata(record(accessions={12742739: "A3244"}), tmp_path)

    assert read_package_metadata(tmp_path).accessions == {"12742739": "A3244"}


def test_the_record_is_frozen():
    with pytest.raises(Exception):
        record().frame_count = 1
