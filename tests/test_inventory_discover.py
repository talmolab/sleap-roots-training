"""Enumeration and version-family grouping.

Covers ``Requirement: Candidate Enumeration`` and ``Requirement: Version Family
Grouping``. The load-bearing point of both is that exclusion cannot be done by directory
alone — measured over one share root, 13,164 of 18,099 ``.slp`` files are
``*.predictions.slp`` and thousands of derived files sit outside every ``models/``,
``predictions/`` and ``train_test_split*/`` directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from inventory_fixtures import build_share_tree, touch_labels
from sleap_roots_training.inventory import discover

# --------------------------------------------------------------------------------------
# Candidate Enumeration
# --------------------------------------------------------------------------------------


def test_a_prediction_file_outside_every_derived_directory_is_excluded(tmp_path):
    """Scenario: A prediction file outside every derived directory is excluded."""
    root = build_share_tree(tmp_path / "share")
    scan = discover.walk(root)

    stray = root / "SLEAP_soybean/primary_6nodes/labels.v002.predictions.slp"
    assert stray not in {c.path for c in scan.candidates}
    assert scan.exclusions[stray] == discover.DERIVED_FILENAME


def test_files_under_a_derived_directory_are_excluded(tmp_path):
    """Scenario: A file under a derived directory is excluded."""
    root = build_share_tree(tmp_path / "share")
    scan = discover.walk(root)

    excluded = {
        p for p, rule in scan.exclusions.items() if rule == discover.DERIVED_DIR
    }
    relative = {p.relative_to(root).as_posix() for p in excluded}
    assert relative == {
        "SLEAP_soybean/models/240101_unet/labels.v001.slp",
        "SLEAP_soybean/predictions/labels.v001.slp",
        "SLEAP_rice/train_test_split_0.8/train.slp",
    }


def test_an_unversioned_labels_file_is_a_candidate(tmp_path):
    """Scenario: An unversioned labels file is a candidate.

    The nine unversioned files under ``SLEAP_medicago_plates/combined_roots/`` are the
    newest labeling on the share, so an absent version suffix must not mean scratch.
    """
    root = build_share_tree(tmp_path / "share")
    scan = discover.walk(root)

    unversioned = root / "SLEAP_medicago_plates/combined_roots/MK24_roots.slp"
    assert unversioned in {c.path for c in scan.candidates}


def test_files_seen_excluded_and_unreadable_directories_reconcile(tmp_path):
    """Scenario: Files seen, files excluded and unreadable directories all reconcile."""
    root = build_share_tree(tmp_path / "share")
    scan = discover.walk(root)

    assert scan.files_seen == 14
    assert len(scan.candidates) + len(scan.exclusions) == scan.files_seen
    assert scan.counts_by_rule[discover.DERIVED_FILENAME] == 2
    assert scan.counts_by_rule[discover.DERIVED_DIR] == 3
    assert scan.unreadable_directories == 0


@pytest.mark.skipif(
    os.name == "nt", reason="chmod 0o000 does not deny listing on Windows"
)
def test_an_unreadable_directory_is_counted_not_swallowed(tmp_path):
    """The walk reports what it could not read.

    ``os.walk`` discards permission errors by default. For a tool whose whole purpose is
    "nobody knows what labeled data exists", a silent undercount is the worst available
    failure: the coverage evidence would be wrong with nothing to show it.
    """
    root = build_share_tree(tmp_path / "share")
    blocked = root / "SLEAP_blocked"
    touch_labels(blocked / "labels.v001.slp")
    blocked.chmod(0o000)
    try:
        scan = discover.walk(root)
    finally:
        blocked.chmod(0o755)

    assert scan.unreadable_directories == 1
    assert blocked in scan.unreadable_paths


def test_the_walk_does_not_follow_symlinks(tmp_path):
    """Pinned so that enabling it later is a deliberate act, not a default."""
    root = build_share_tree(tmp_path / "share")
    outside = tmp_path / "outside"
    touch_labels(outside / "labels.v009.slp")
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted here")

    scan = discover.walk(root)
    assert not [c for c in scan.candidates if "link" in c.path.as_posix()]


# --------------------------------------------------------------------------------------
# Version Family Grouping
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,stem,version,suffix",
    [
        ("labels.v001.slp", "labels", 1, ".slp"),
        ("labels.v002.pkg.slp", "labels", 2, ".pkg.slp"),
        ("labels.v001_ana.slp", "labels_ana", 1, ".slp"),
        ("labels.combined.v003.slp", "labels.combined", 3, ".slp"),
    ],
)
def test_all_four_version_suffix_shapes_parse(name, stem, version, suffix):
    """All four shapes occur on the share, two of them inside one five-file family."""
    parsed = discover.parse_version(Path(name))
    assert (parsed.stem, parsed.version, parsed.suffix) == (stem, version, suffix)


def test_an_unversioned_name_parses_with_no_version():
    """An unversioned file is still a family, of one."""
    parsed = discover.parse_version(Path("MK24_roots.slp"))
    assert parsed.version is None
    assert parsed.stem == "MK24_roots"


def test_identical_basenames_in_different_directories_stay_separate(tmp_path):
    """Scenario: Identical basenames in different directories stay separate.

    ``labels.vNNN.slp`` alone occurs 57 times across 23 directories spanning five species
    and both capture modes, so keying on the basename would let one file supersede 56
    unrelated ones.
    """
    root = build_share_tree(tmp_path / "share")
    families = discover.group(discover.walk(root).candidates)

    holding = [f for f in families if f.stem == "labels" and f.suffix == ".slp"]
    directories = {f.directory.relative_to(root).as_posix() for f in holding}
    assert directories == {
        "SLEAP_soybean/primary_6nodes",
        "SLEAP_rice/primary_6nodes",
    }
    for family in holding:
        assert family.latest.path.parent == family.directory


def test_trailing_text_after_the_version_keeps_families_apart(tmp_path):
    """Scenario: Trailing text after the version keeps families apart."""
    root = build_share_tree(tmp_path / "share")
    families = discover.group(discover.walk(root).candidates)

    directory = root / "SLEAP_soybean/primary_6nodes"
    per_labeler = [f for f in families if f.directory == directory and "_" in f.stem]
    assert sorted(f.stem for f in per_labeler) == ["labels_ana", "labels_ben"]
    assert all(len(f.members) == 1 for f in per_labeler)


def test_a_packaged_twin_is_cross_referenced_not_merged(tmp_path):
    """Scenario: A packaged twin is cross-referenced, not merged.

    A ``.slp`` and a ``.pkg.slp`` at one version are the same labeling effort in two
    representations — one references images, one embeds them — so they are reported
    together without the suffix chain collapsing them into one family.
    """
    root = build_share_tree(tmp_path / "share")
    families = discover.group(discover.walk(root).candidates)

    directory = root / "SLEAP_soybean/primary_6nodes"
    plain = next(
        f
        for f in families
        if f.directory == directory and f.suffix == ".slp" and f.stem == "labels"
    )
    packaged = next(f for f in families if f.suffix == ".pkg.slp")
    assert plain.key != packaged.key
    assert packaged.key in plain.twins
    assert plain.key in packaged.twins
