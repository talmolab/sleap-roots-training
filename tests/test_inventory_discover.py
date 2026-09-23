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


# --------------------------------------------------------------------------------------
# Regressions from the PR #58 review. Each of these failed when written.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "scan_001_predictions.slp",
        "arabidopsis-primary_v000_on_sorghum-primary_v000_test_predictions.slp",
        "day5predictions.slp",
        "predictions.slp",
    ],
)
def test_prediction_output_is_excluded_whatever_separator_precedes_it(tmp_path, name):
    """The rule matched a dot; the corpus overwhelmingly uses an underscore.

    603 of 1,250 rows in the first committed scan were derived output, 416 of them
    carrying zero user instances and non-zero predictions — the tool read the evidence
    they were derived and emitted them anyway.
    """
    root = tmp_path / "share"
    touch_labels(root / "SLEAP_soybean" / "primary" / name)

    scan = discover.walk(root)

    assert not scan.candidates
    assert scan.exclusions[root / "SLEAP_soybean" / "primary" / name] == (
        discover.DERIVED_FILENAME
    )


@pytest.mark.parametrize(
    "name", ["labels_gt.train.slp", "labels_gt.val.slp", "labels_pr.test.slp"]
)
def test_ground_truth_and_predicted_splits_are_excluded(tmp_path, name):
    """`labels_gt.*` / `labels_pr.*` are train/val/test splits, not labeling efforts."""
    root = tmp_path / "share"
    touch_labels(root / "experiments" / "artifacts" / "soybean-primary_v001" / name)

    scan = discover.walk(root)
    assert not scan.candidates


def test_files_under_a_sleap_nn_run_directory_are_excluded(tmp_path):
    """`<timestamp>.<model_type>.n=<N>` is a training run, not a collection."""
    root = tmp_path / "share"
    run = root / "SLEAP_Soy" / "lateral" / "221006_172103.multi_instance.n=482"
    touch_labels(run / "labels.v001.slp")

    scan = discover.walk(root)
    assert not scan.candidates


def test_a_directory_merely_starting_with_train_test_split_is_not_excluded(tmp_path):
    """`startswith` swallowed `train_test_splitter/`, which is not a split directory."""
    root = tmp_path / "share"
    keep = root / "SLEAP_wheat" / "train_test_splitter" / "labels.v003.slp"
    drop = root / "SLEAP_wheat" / "train_test_split_0.8" / "train.slp"
    touch_labels(keep)
    touch_labels(drop)

    scan = discover.walk(root)

    assert keep in {c.path for c in scan.candidates}
    assert scan.exclusions[drop] == discover.DERIVED_DIR


def test_the_two_trailing_text_shapes_are_different_families(tmp_path):
    """`.vNNN_<text>.slp` and `.<text>.vNNN.slp` are named as distinct by the spec.

    They collapsed to one key, so one file became `latest` and the other appeared
    nowhere in either artifact — the exact harm the requirement exists to prevent.
    """
    directory = tmp_path / "share" / "SLEAP_soybean" / "primary"
    touch_labels(directory / "labels.v001_ana.slp")
    touch_labels(directory / "labels_ana.v001.slp")

    families = discover.group(discover.walk(tmp_path / "share").candidates)

    assert len(families) == 2
    assert all(len(f.members) == 1 for f in families)


def test_zero_padding_variants_are_one_family_with_both_members_kept(tmp_path):
    """`v1`, `v01` and `v001` are the same version — one family, three members.

    Collapsing them is right; losing them is not. Every candidate must stay reachable.
    """
    directory = tmp_path / "share" / "SLEAP_rice" / "primary"
    for name in ("labels.v1.slp", "labels.v01.slp", "labels.v001.slp"):
        touch_labels(directory / name)

    families = discover.group(discover.walk(tmp_path / "share").candidates)

    assert len(families) == 1
    assert len(families[0].members) == 3


def test_suffix_case_does_not_split_a_family():
    """`train.v2.SLP` and `train.v2.slp` are one effort, not two.

    Asserted at the parser, not through the filesystem: Windows is case-insensitive, so
    a two-file fixture would silently be one file and the test would pass vacuously.
    """
    lower = discover.parse_version(Path("labels.v002.slp"))
    upper = discover.parse_version(Path("labels.v002.SLP"))

    assert (lower.stem, lower.version, lower.suffix) == (
        upper.stem,
        upper.version,
        upper.suffix,
    )


def test_every_candidate_belongs_to_exactly_one_family(tmp_path):
    """Nothing may vanish between enumeration and grouping."""
    root = build_share_tree(tmp_path / "share")
    scan = discover.walk(root)
    families = discover.group(scan.candidates)

    assert sum(len(f.members) for f in families) == len(scan.candidates)


def test_an_onerror_with_no_filename_does_not_kill_the_scan(tmp_path):
    """`OSError.filename` can be None, and `Path(None)` raises.

    This is the one callback whose entire purpose is that an 18,099-file scan must not
    die on one bad directory.
    """
    root = build_share_tree(tmp_path / "share")
    real_walk = discover.os.walk

    def _walk(top, onerror=None, followlinks=False):
        onerror(OSError(13, "Permission denied"))
        return real_walk(top, onerror=onerror, followlinks=followlinks)

    original = discover.os.walk
    discover.os.walk = _walk
    try:
        scan = discover.walk(root)
    finally:
        discover.os.walk = original

    assert scan.unreadable_directories == 1
    assert scan.candidates
