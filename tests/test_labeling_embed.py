"""The embed guarantee: a built package does not depend on paths that outlive it.

This is the change issue #26 exists for, isolated into its own file because its failure
mode is the one already in production. Six of the eight collections in
``wandb-registry-sleap-roots-labels`` carry ``repaired_from: "v0"`` /
``embedded-images-repair``: the external reference broke — a dead temp dir, an unreachable
``Z:`` drive — and someone hand-patched the file into a package afterwards. That repair is
one-way, because ``save_slp`` restores the original video only "if available", so a
repaired package is capped at whatever frames were embedded at repair time.

design.md Decision 2 puts the fix in the *builder* rather than in ``#10``'s
``publish-labels``, so the on-disk package is already a complete artifact — anyone who
builds one and inspects it before publishing gets the guarantee, not the broken reference.
"""

from __future__ import annotations

import shutil

import pytest
import sleap_io as sio

from test_labeling_build_package import METADATA, build_inputs, primary
from sleap_roots_training.labeling.build_package import build_slp_project
from sleap_roots_training.labeling.validate import (
    assert_slp_is_self_contained,
    slp_is_self_contained,
)


def build_and_orphan(tmp_path):
    """Build a package, then destroy every path its ``.slp`` could reference.

    Reproduces the failure that produced the six repaired collections: the images are
    gone and there is no ``Z:`` drive to go back to.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)
    shutil.rmtree(images_dir)
    return output_dir


def test_the_built_slp_still_yields_its_frames_with_the_images_gone(tmp_path):
    """Task 5.1. Against the section-4 port this fails, which is the point of the commit."""
    output_dir = build_and_orphan(tmp_path)

    labels = primary(output_dir)

    assert len(labels.labeled_frames) == 6
    # Reading pixels is the real test: a package that lists its frames but cannot show
    # them is exactly the state a labeler discovers on opening it, not before.
    for lf in labels.labeled_frames:
        assert lf.image.shape[0] > 0


def test_the_built_slp_reports_itself_self_contained(tmp_path):
    output_dir = build_and_orphan(tmp_path)

    for path in output_dir.glob("*.slp"):
        assert slp_is_self_contained(path), path


def test_a_moved_package_is_still_readable(tmp_path):
    """The package directory is the handoff, so it has to survive being handed over."""
    output_dir = build_and_orphan(tmp_path)
    moved = tmp_path / "elsewhere/package"
    moved.parent.mkdir()
    shutil.move(str(output_dir), str(moved))

    labels = sio.load_slp(str(moved / "soybean_weep_primary_labels.v000.slp"))

    # Frame *count* survives a broken reference — a labeler only discovers the breakage
    # on trying to see a frame — so the assertion has to reach the pixels.
    assert len(labels.labeled_frames) == 6
    assert labels.labeled_frames[0].image.shape[0] > 0


# --------------------------------------------------------------------------------------
# Task 5.3 — the guarantee holds against a package this builder did not produce
# --------------------------------------------------------------------------------------


def test_validation_rejects_an_external_reference_slp(tmp_path):
    """An older tool or a hand-assembled package must not pass as self-contained.

    This is what makes the guarantee a property of the *package* rather than of the code
    path that happened to write it — the check ``#10``'s ``publish-labels`` calls before
    upload (design.md Decision 2).
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)
    external = tmp_path / "external.slp"
    sio.save_slp(primary(output_dir), str(external), embed=False)

    assert not slp_is_self_contained(external)
    with pytest.raises(ValueError, match="not self-contained"):
        assert_slp_is_self_contained(external)


def test_the_rejection_names_the_file_and_an_external_path(tmp_path):
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(tmp_path)
    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)
    external = tmp_path / "external.slp"
    sio.save_slp(primary(output_dir), str(external), embed=False)

    with pytest.raises(ValueError) as excinfo:
        assert_slp_is_self_contained(external)

    assert "external.slp" in str(excinfo.value)
    assert "A3244_9DK8KJJEZR_age3_0.jpg" in str(excinfo.value)


def test_a_built_package_passes_the_same_check_that_rejects_the_external_one(tmp_path):
    """The check and the builder agree, so the guarantee is not asserted only by its author."""
    output_dir = build_and_orphan(tmp_path)

    for path in sorted(output_dir.glob("*.slp")):
        assert_slp_is_self_contained(path)
