"""Reading per-file facts out of the labels files themselves.

Covers ``Requirement: Per-File Labeling Facts``. Everything here is derived from the file
— nothing is inferred from a name, and nothing is fetched.
"""

from __future__ import annotations

from pathlib import Path

import sleap_io as sio

from inventory_fixtures import write_labels
from sleap_roots_training.inventory import read


def test_facts_are_recorded_per_file(tmp_path):
    """Scenario: Facts are recorded per file."""
    path = write_labels(
        tmp_path / "labels.v001.slp",
        skeleton_names=("soybean_primary",),
        node_names=("r1", "r2", "r3"),
        n_frames=2,
        n_user=1,
        n_pred=2,
    )

    facts = read.read_facts(path)

    assert facts.error is None
    assert facts.skeleton_names == ("soybean_primary",)
    assert facts.node_names == ("r1", "r2", "r3")
    assert facts.node_count == 3
    assert facts.frame_count == 2
    assert facts.user_instances == 2
    assert facts.predicted_instances == 4
    assert [Path(p).name for p in facts.video_filenames] == ["f0.jpg", "f1.jpg"]


def test_the_instance_counts_come_from_the_labels_level_accessors(tmp_path):
    """`sleap_io` 0.7.1 spells them `n_user_instances` / `n_pred_instances`.

    Only ``user_instances`` / ``predicted_instances`` are absent at the ``Labels`` level.
    The accessors that do exist read the instance store directly when the file is loaded
    lazily, so hand-summing over ``LabeledFrame`` forfeits that across ~1,450 candidates.
    """
    path = write_labels(tmp_path / "labels.v001.slp", n_frames=3, n_user=2, n_pred=1)
    labels = sio.load_slp(str(path))

    assert not hasattr(sio.Labels, "user_instances")
    assert not hasattr(sio.Labels, "predicted_instances")
    assert labels.n_user_instances == 6
    assert labels.n_pred_instances == 3

    facts = read.read_facts(path)
    assert (facts.user_instances, facts.predicted_instances) == (6, 3)


def test_zero_and_multiple_skeletons_are_distinguished(tmp_path):
    """Scenario: Zero and multiple skeletons are distinguished.

    ``Labels.skeleton`` raises ``ValueError`` for both, differing only in message, so the
    two are separated on ``len(Labels.skeletons)`` rather than on the exception — the
    message is an upstream string this repo does not own.
    """
    none = write_labels(tmp_path / "none.v001.slp", skeleton_names=(), n_user=0)
    several = write_labels(
        tmp_path / "several.v001.slp", skeleton_names=("Skeleton-1", "Skeleton-2")
    )

    no_skeleton = read.read_facts(none)
    multiple = read.read_facts(several)

    assert no_skeleton.skeleton_state == read.NO_SKELETON
    assert no_skeleton.skeleton_names == ()
    assert no_skeleton.node_count is None
    assert no_skeleton.error is None

    assert multiple.skeleton_state == read.MULTIPLE_SKELETONS
    assert multiple.skeleton_names == ("Skeleton-1", "Skeleton-2")
    assert multiple.error is None

    assert no_skeleton.skeleton_state != multiple.skeleton_state


def test_a_single_skeleton_is_its_own_state(tmp_path):
    """The ordinary case, so the two failure states are not the only branches."""
    path = write_labels(tmp_path / "one.v001.slp")
    assert read.read_facts(path).skeleton_state == read.SINGLE_SKELETON


def test_an_unreadable_file_does_not_abort_the_scan(tmp_path):
    """Scenario: An unreadable file does not abort the scan.

    The fixture is genuinely corrupt rather than merely odd. The catch has to be broad
    enough for ``TypeError``: a labels file whose video was built from a filename *list*
    raises that from inside ``sleap_io``, not the ``ValueError`` or ``OSError`` an
    implementer would code for.
    """
    good = write_labels(tmp_path / "good.v001.slp")
    corrupt = tmp_path / "corrupt.v001.slp"
    corrupt.write_bytes(b"not an hdf5 file at all")

    facts = [read.read_facts(p) for p in (corrupt, good)]

    assert facts[0].error is not None
    assert facts[0].frame_count is None
    assert facts[1].error is None
    assert facts[1].frame_count == 1


def test_a_broad_failure_is_caught_not_propagated(tmp_path, monkeypatch):
    """A `TypeError` from deep inside the reader is recorded, not raised."""

    def _boom(*_args, **_kwargs):
        raise TypeError("expected str, bytes or os.PathLike object, not list")

    monkeypatch.setattr(read.sio, "load_slp", _boom)
    facts = read.read_facts(tmp_path / "whatever.v001.slp")

    assert facts.error is not None
    assert "not list" in facts.error
