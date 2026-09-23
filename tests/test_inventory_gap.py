"""The `skeletons.yaml` keying gap — the headline finding.

Covers ``Requirement: Skeleton Table Keying Gap``. `lookup_skeleton` is keyed
``(species, root_type, age)`` and takes no ``mode``, so a cylinder family and a plate
family of the same species and root type select the same row however far apart their
node counts are. Node counts come from the files and the mode is name-derived from the
path, so none of this needs a scan database or any other external service.
"""

from __future__ import annotations

import wandb

from inventory_fixtures import write_labels
from sleap_roots_training.inventory import discover, gap, read
from sleap_roots_training.labeling.skeletons import SkeletonRow


def _observe(path):
    """Pair one file with its family, the way a scan does."""
    candidate = discover.Candidate(path=path, parsed=discover.parse_version(path))
    family = discover.group([candidate])[0]
    return gap.Observed(family=family, facts=read.read_facts(path))


def test_two_capture_modes_select_one_row(tmp_path, monkeypatch):
    """Scenario: Two capture modes select one row.

    Also asserts the report reaches no network: the repo's own registry tests install
    this guard because an unguarded read-back would load ``~/.netrc`` and hit
    api.wandb.ai from a unit test.
    """

    def _no_api(*_args, **_kwargs):
        raise AssertionError("the gap report must not construct a wandb.Api")

    monkeypatch.setattr(wandb, "Api", _no_api)

    cylinder = write_labels(
        tmp_path / "cyl_arabidopsis_primary_6nodes" / "labels.v001.slp",
        skeleton_names=("arabidopsis_primary",),
        node_names=tuple(f"r{i}" for i in range(1, 7)),
    )
    plate = write_labels(
        tmp_path / "plate_arabidopsis_primary_8nodes" / "labels.v001.slp",
        skeleton_names=("arabidopsis_primary",),
        node_names=tuple(f"r{i}" for i in range(1, 9)),
    )

    report = gap.build_report([_observe(cylinder), _observe(plate)])

    assert len(report.mode_collisions) == 1
    collision = report.mode_collisions[0]
    assert collision.species == "arabidopsis"
    assert collision.root_type == "primary"
    assert set(collision.modes) == {"cylinder", "plate"}
    assert sorted(collision.node_counts) == [6, 8]
    assert collision.row_age is None


def test_a_species_with_no_row_is_reported(tmp_path):
    """Scenario: A species with no row is reported.

    The table is injected rather than taken from the package, so adding a real wheat row
    later corrects the corpus without breaking this test.
    """
    table = (
        SkeletonRow(species="soybean", root_type="primary", age=None, node_count=6),
    )
    path = write_labels(
        tmp_path / "SLEAP_wheat" / "seminal" / "labels_sr_5-14DAG.v004.slp",
        skeleton_names=("Skeleton-1",),
    )

    report = gap.build_report([_observe(path)], table=table)

    assert "wheat" in report.uncovered_species


def test_the_packaged_table_really_has_no_row_for_the_shares_species():
    """Guards the claim the requirement rests on, against the real packaged table."""
    uncovered = gap.uncovered(
        {"wheat", "sorghum", "medicago", "alfalfa", "covercress", "soybean"}
    )
    assert uncovered == {"wheat", "sorghum", "medicago", "alfalfa", "covercress"}


def test_an_auto_generated_skeleton_name_is_unparseable(tmp_path):
    """Scenario: An auto-generated skeleton name is unparseable.

    ``"Skeleton-1".partition("_")`` yields ``('Skeleton-1', '', '')`` — an empty root
    type — so the weekly check at ``tests/test_labeling_skeletons.py:419`` cannot resolve
    it, and neither can anything else keyed that way.
    """
    path = write_labels(
        tmp_path / "SLEAP_sorghum" / "primary_6nodes" / "labels.v001.slp",
        skeleton_names=("Skeleton-1", "Skeleton-2"),
    )

    report = gap.build_report([_observe(path)])

    assert report.unparseable_skeletons
    entry = report.unparseable_skeletons[0]
    assert entry.skeleton_names == ("Skeleton-1", "Skeleton-2")
    assert "Skeleton-1".partition("_") == ("Skeleton-1", "", "")


def test_a_parseable_skeleton_name_is_not_flagged(tmp_path):
    """The ordinary case stays quiet, so the flag means something."""
    path = write_labels(
        tmp_path / "SLEAP_soybean" / "primary_6nodes" / "labels.v001.slp",
        skeleton_names=("soybean_primary",),
    )
    assert not gap.build_report([_observe(path)]).unparseable_skeletons


def test_species_mode_and_root_type_are_labelled_name_derived(tmp_path):
    """Nothing here is evidence, and the report has to say so."""
    path = write_labels(
        tmp_path / "cyl_soybean_primary_6nodes" / "labels.v001.slp",
        skeleton_names=("soybean_primary",),
    )
    derived = gap.derive(_observe(path).family)

    assert (derived.species, derived.mode, derived.root_type) == (
        "soybean",
        "cylinder",
        "primary",
    )
    assert derived.source == gap.NAME_DERIVED


def test_wheats_seminal_nickname_derives_the_crown_root_type(tmp_path):
    """The team calls wheat's seminal roots crown; `RootType` gains no member."""
    path = write_labels(
        tmp_path / "SLEAP_wheat" / "seminal" / "labels_sr_5-14DAG.v004.slp",
        skeleton_names=("Skeleton-1",),
    )
    assert gap.derive(_observe(path).family).root_type == "crown"


# --------------------------------------------------------------------------------------
# Regressions from the PR #58 review.
# --------------------------------------------------------------------------------------


def test_mode_is_derived_from_the_whole_path_not_the_last_three_parts(tmp_path):
    """The window bug moved the headline number 36%.

    `_tokens` read `directory.parts[-3:]` for mode while species read the whole path, so
    any `plates` token more than three directories up was invisible. On the real corpus
    that hid 4 plate-arabidopsis families entirely and undercounted the 8-node ones
    11 versus 15.
    """
    deep = (
        tmp_path
        / "SLEAP_arabidopsis_plates"
        / "run_20250708"
        / "inputs"
        / "primary_root_8nodes"
        / "labels.v001.slp"
    )
    write_labels(deep, skeleton_names=("arabidopsis_primary",))

    assert gap.derive(_observe(deep).family).mode == "plate"


def test_soy_is_soybean(tmp_path):
    """The committed report told a reader that `soy` is not a species.

    `SLEAP_Soy/` yields `soy`; 34 families carried it, listed as "not species; tokens
    read off a path", alongside 49 listed as `soybean`.
    """
    path = write_labels(tmp_path / "SLEAP_Soy" / "lateral" / "labels.v001.slp")
    assert gap.derive(_observe(path).family).species == "soybean"


def test_a_zero_node_skeleton_is_not_silently_dropped(tmp_path):
    """`if ... and node_count:` made a 0-node skeleton falsy, so it vanished.

    It was discarded from collision analysis exactly like an unreadable file.
    """
    path = write_labels(
        tmp_path / "cyl_soybean_primary" / "labels.v001.slp",
        skeleton_names=("soybean_primary",),
        node_names=(),
    )
    facts = _observe(path).facts
    assert facts.skeleton_state != read.NO_SKELETON
    assert facts.node_count == 0


def test_the_report_states_how_much_of_the_corpus_it_analysed(tmp_path):
    """The finding rested on 47 of 1,250 families with no denominator given."""
    one = write_labels(
        tmp_path / "cyl_arabidopsis_primary_6nodes" / "labels.v001.slp",
        skeleton_names=("arabidopsis_primary",),
        node_names=tuple(f"r{i}" for i in range(1, 7)),
    )
    two = write_labels(
        tmp_path / "unknowable" / "labels.v001.slp", skeleton_names=("Skeleton-1",)
    )

    report = gap.build_report([_observe(one), _observe(two)])

    assert report.families_considered == 2
    assert report.families_analysed == 1
    assert report.families_skipped_reasons["no-mode"] == 1
