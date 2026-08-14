"""The package layout contract, extracted during the blocking review of #40.

These constants and the project-filename rule lived in ``validate.py``, so every module
that *writes* a package imported the module that *checks* it. That inversion is also how
``project_filename`` came to be duplicated: its docstring said the naming was "stated once",
while ``build_slp_project`` re-typed the same f-string beside its own ``save_slp`` call.

The point of this module having its own tests is that the layout is a contract between the
writers and the checker, and #10's ``publish-labels`` is a third party to it.
"""

from __future__ import annotations

import pytest

from conftest import package_record
from sleap_roots_training.labeling import layout
from sleap_roots_training.labeling.metadata import PackageMetadata

METADATA = PackageMetadata(
    species="soybean",
    mode="cylinder",
    experiment="weep",
    root_types=("primary", "lateral"),
)


def test_the_project_filename_follows_the_command_docs_naming():
    assert (
        layout.project_filename(METADATA, "primary", "v000")
        == "soybean_weep_primary_labels.v000.slp"
    )


def test_the_builder_and_the_validator_derive_the_same_name():
    """The duplication this module exists to remove: two spellings of one rule.

    ``build_slp_project`` names the file from the identity it was handed, before it has a
    record; ``validate_package`` names it from the record it read back off disk. They have
    to agree, or validation looks for a file the builder never wrote.
    """
    record = package_record()
    for root_type in METADATA.root_types:
        assert layout.project_filename_for(
            record, root_type
        ) == layout.project_filename(record.metadata, root_type, record.version)


@pytest.mark.parametrize(
    "name", [".DS_Store", "Thumbs.db", "desktop.ini", "._image.jpg"]
)
def test_operating_system_sidecars_are_recognized(name):
    assert layout.is_sidecar(name)


@pytest.mark.parametrize(
    "name", ["A3244_9DK8KJJEZR_age3_view001.jpg", "sample_manifest.csv", "_leading.jpg"]
)
def test_real_content_is_not_mistaken_for_a_sidecar(name):
    assert not layout.is_sidecar(name)
