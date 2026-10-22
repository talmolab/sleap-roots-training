"""Where `skeletons.yaml` cannot express the corpus.

Covers ``Requirement: Skeleton Table Mode Gap``. Rows carry a ``mode``, so a family is
matched on species, mode and root type; what the table can still fail to express is a
mode the corpus uses and the table has no row for, or a node count the matched row does
not have. Node counts come from the files and the mode is name-derived from the path, so
none of this needs a scan database or any other external service.
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


def _family(rel):
    """A family built from a relative path, with no file on disk.

    ``derive()`` reads a family's whole path, and pytest names ``tmp_path`` after the
    test, so a temp directory can supply a species, mode or root-type token (#78).
    """
    path = gap.Path(rel)
    parsed = discover.parse_version(path)
    return discover.Family(
        directory=path.parent, stem=parsed.stem, suffix=parsed.suffix
    )


def _row(species, mode, root_type, node_count, age=None):
    """One injected table row, built inside a test rather than at module scope."""
    return SkeletonRow(
        species=species,
        mode=mode,
        root_type=root_type,
        age=age,
        node_count=node_count,
    )


def _nodes(count):
    return tuple(f"r{i}" for i in range(1, count + 1))


def test_an_observed_mode_with_no_row_is_reported(tmp_path):
    """Scenario: An observed mode with no row is reported.

    The committed scan's own case: 10 plate arabidopsis lateral families at 3 nodes, and
    the table has arabidopsis lateral only in cylinder.
    """
    table = (_row("arabidopsis", "cylinder", "lateral", 4),)
    path = write_labels(
        tmp_path / "plate_arabidopsis_lateral_3nodes" / "labels.v001.slp",
        skeleton_names=("Skeleton-1",),
        node_names=_nodes(3),
    )

    report = gap.build_report([_observe(path)], table=table)

    assert len(report.mode_gaps) == 1
    found = report.mode_gaps[0]
    assert (found.species, found.mode, found.root_type) == (
        "arabidopsis",
        "plate",
        "lateral",
    )
    assert found.table_modes == ("cylinder",)
    assert found.node_counts == (3,)
    assert len(found.paths) == 1


def test_a_mode_with_its_own_row_is_not_a_gap(tmp_path, monkeypatch):
    """Scenario: A mode with its own row is not a gap.

    The inverse of what the mode-blind table reported as its headline. Also asserts the
    report reaches no network: the repo's own registry tests install this guard because
    an unguarded read-back would load ``~/.netrc`` and hit api.wandb.ai from a unit test.
    """

    def _no_api(*_args, **_kwargs):
        raise AssertionError("the gap report must not construct a wandb.Api")

    monkeypatch.setattr(wandb, "Api", _no_api)
    table = (
        _row("arabidopsis", "cylinder", "primary", 6),
        _row("arabidopsis", "plate", "primary", 8, age="2, 3, 4, 5, 6, 7"),
    )
    cylinder = write_labels(
        tmp_path / "cyl_arabidopsis_primary_6nodes" / "labels.v001.slp",
        skeleton_names=("arabidopsis_primary",),
        node_names=_nodes(6),
    )
    plate = write_labels(
        tmp_path / "plate_arabidopsis_primary_8nodes" / "labels.v001.slp",
        skeleton_names=("arabidopsis_primary",),
        node_names=_nodes(8),
    )

    report = gap.build_report([_observe(cylinder), _observe(plate)], table=table)

    assert report.families_analysed == 2
    assert report.mode_gaps == []
    assert report.node_count_disagreements == []


def test_an_uncovered_species_is_not_a_mode_gap(tmp_path):
    """Scenario: An uncovered species is not a mode gap. It is reported once, as uncovered."""
    table = (_row("soybean", "cylinder", "lateral", 4),)
    path = write_labels(
        tmp_path / "SLEAP_medicago_plates" / "lateral" / "labels.v001.slp",
        skeleton_names=("Skeleton-0",),
        node_names=_nodes(3),
    )

    report = gap.build_report([_observe(path)], table=table)

    assert "medicago" in report.uncovered_species
    assert report.mode_gaps == []


def test_a_covered_species_whose_root_type_has_no_row_is_neither(tmp_path):
    """Rice has rows, but no lateral row in any mode: not a mode gap, not uncovered."""
    table = (_row("rice", "cylinder", "crown", 6, age="2, 3, 4, 5"),)
    path = write_labels(
        tmp_path / "plate_rice_lateral" / "labels.v001.slp",
        skeleton_names=("Skeleton-0",),
        node_names=_nodes(4),
    )

    report = gap.build_report([_observe(path)], table=table)

    assert report.families_analysed == 1
    assert report.mode_gaps == []
    assert report.node_count_disagreements == []
    assert "rice" not in report.uncovered_species


def test_a_mode_gap_aggregates_node_counts_across_families(tmp_path):
    table = (_row("arabidopsis", "cylinder", "lateral", 4),)
    three = write_labels(
        tmp_path / "plate_arabidopsis_lateral_a" / "labels.v001.slp",
        node_names=_nodes(3),
    )
    four = write_labels(
        tmp_path / "plate_arabidopsis_lateral_b" / "labels.v001.slp",
        node_names=_nodes(4),
    )

    report = gap.build_report([_observe(three), _observe(four)], table=table)

    assert len(report.mode_gaps) == 1
    assert report.mode_gaps[0].node_counts == (3, 4)
    assert len(report.mode_gaps[0].paths) == 2


def test_a_disagreeing_node_count_is_reported(tmp_path):
    """Scenario: A disagreeing node count is reported. Printed, not resolved.

    The committed scan's own case: plate arabidopsis primary families at 7 nodes sit in a
    directory named `primary_root_8nodes`, beside the 8-node files the row describes.
    """
    table = (_row("arabidopsis", "plate", "primary", 8, age="2, 3, 4, 5, 6, 7"),)
    agrees = write_labels(
        tmp_path / "plate_arabidopsis_primary_a" / "labels.v001.slp",
        node_names=_nodes(8),
    )
    disagrees = write_labels(
        tmp_path / "plate_arabidopsis_primary_b" / "labels.v001.slp",
        node_names=_nodes(7),
    )

    report = gap.build_report([_observe(agrees), _observe(disagrees)], table=table)

    assert report.mode_gaps == []
    assert len(report.node_count_disagreements) == 1
    found = report.node_count_disagreements[0]
    assert (found.species, found.mode, found.root_type) == (
        "arabidopsis",
        "plate",
        "primary",
    )
    assert found.row_node_counts == (8,)
    assert found.observed == (7,)
    assert len(found.paths) == 1


def test_counts_matching_any_window_of_the_mode_are_not_a_disagreement(tmp_path):
    """Age is not derivable from a path, so a count matching *any* window agrees.

    Rice crown split at 6 and 9 nodes, with families at both: neither is reported.
    """
    table = (
        _row("rice", "cylinder", "crown", 6, age="2, 3, 4, 5"),
        _row("rice", "cylinder", "crown", 9, age="6, 7, 8"),
    )
    six = write_labels(
        tmp_path / "cyl_rice_crown_a" / "labels.v001.slp", node_names=_nodes(6)
    )
    nine = write_labels(
        tmp_path / "cyl_rice_crown_b" / "labels.v001.slp", node_names=_nodes(9)
    )

    report = gap.build_report([_observe(six), _observe(nine)], table=table)

    assert report.families_analysed == 2
    assert report.node_count_disagreements == []


def test_a_species_with_no_row_is_reported(tmp_path):
    """Scenario: A species with no row is reported.

    The table is injected rather than taken from the package, so adding a real wheat row
    later corrects the corpus without breaking this test.
    """
    table = (
        SkeletonRow(
            species="soybean",
            mode="cylinder",
            root_type="primary",
            age=None,
            node_count=6,
        ),
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
    type — so ``test_the_table_agrees_with_the_published_label_collections`` cannot
    resolve it, and neither can anything else keyed that way.
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


def test_wheats_nickname_derives_the_third_row():
    """The team calls wheat's seminal roots crown; `RootType` gains no member.

    Built from a relative family: under ``tmp_path`` this test's own temp directory,
    ``test_wheats_seminal_nickname_d0``, supplied ``seminal`` and could not fail (#78).
    """
    family = _family("SLEAP_wheat/seminal/labels_sr_5-14DAG.v004.slp")
    assert gap.derive(family).root_type == "crown"


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


# --------------------------------------------------------------------------------------
# update-inventory-derivation — Filename-First Species Derivation
# --------------------------------------------------------------------------------------


def test_the_filename_beats_the_folder():
    """Wheat plate labels sit in an arabidopsis folder; the filename says wheat."""
    derived = gap.derive(
        _family(
            "SLEAP_arabidopsis_plates/labels/primary_8nodes/labels_wheat_2-3DAG.v002.slp"
        )
    )

    assert derived.species == "wheat"
    assert derived.species_from == "filename"
    assert derived.species_named == ("wheat",)
    assert derived.folder_species == ("arabidopsis",)
    assert derived.flags == ("folder-species-differs",)


def test_an_alias_in_the_filename_is_read_and_compared():
    derived = gap.derive(
        _family("SLEAP_sorghum/lateral_4nodes/labels_soy_lateral_4nodes.v001.slp")
    )

    assert derived.species == "soybean"
    assert "folder-species-differs" in derived.flags


def test_a_glued_only_prefix_is_read_and_a_bare_one_is_not():
    glued = gap.derive(
        _family("generalizability/x/labels_ONLYpennycress_6nodes.v000.slp")
    )
    bare = gap.derive(_family("generalizability/x/labels_7DAP_laterals_ONLY.v007.slp"))

    assert glued.species == "pennycress"
    assert bare.species is None
    assert bare.flags == ()


def test_a_filename_naming_several_derives_none():
    """Never the first species named, and never the folder's (#59)."""
    derived = gap.derive(
        _family(
            "SLEAP_medicago/primary_root/labels_canola_pennycress_arabidopsis.v015.slp"
        )
    )

    assert derived.species is None
    assert derived.species_named == ("arabidopsis", "canola", "pennycress")
    assert derived.species_from == "filename"
    assert derived.flags == ("multi-species",)


def test_a_folder_naming_several_derives_none():
    derived = gap.derive(
        _family("SLEAP_Canola_Pennycress/primary_root/AAP_primary_root_labels.v001.slp")
    )

    assert derived.species is None
    assert derived.species_named == ("canola", "pennycress")
    assert derived.species_from == "folder"
    assert derived.flags == ("multi-species",)


def test_an_unnamed_file_falls_back_to_the_folder():
    """Characterisation of the species; the new fields are pinned alongside."""
    derived = gap.derive(_family("SLEAP_Soy/lateral/labels.v001.slp"))

    assert derived.species == "soybean"
    assert derived.species_from == "folder"
    assert derived.species_named == ("soybean",)
    assert derived.flags == ()


def test_an_open_folder_word_is_kept_and_contradicts_nothing():
    unnamed = gap.derive(_family("SLEAP_packages_10-24-23/labels.v001.slp"))
    named = gap.derive(_family("SLEAP_packages_10-24-23/labels_rice_3do.v001.slp"))

    assert unnamed.species == "packages"
    assert named.species == "rice"
    assert "folder-species-differs" not in named.flags


def test_a_folder_naming_the_filenames_crop_among_several_contradicts_nothing():
    derived = gap.derive(
        _family(
            "experiments/x_sorghum_soybean_canola_pennycress_rice_arabidopsis_on_y/"
            "labels_rice_3do.v001.slp"
        )
    )

    assert derived.species == "rice"
    assert derived.flags == ()


def test_a_filename_crop_outside_a_pooled_folder_is_flagged():
    derived = gap.derive(
        _family("SLEAP_Canola_Pennycress/primary_root/labels_wheat_5DAG.v001.slp")
    )

    assert derived.species == "wheat"
    assert derived.flags == ("folder-species-differs",)


def test_a_pooled_nickname_file_derives_no_species():
    """#11's specific doubt: the pooled wheat+rice set behind the wheat collection."""
    derived = gap.derive(
        _family(
            "SLEAP_wheat/seminal/labels_seminal_wheat_5-14DAG_rice_3-10DAG.v005.slp"
        )
    )

    assert derived.species is None
    assert derived.flags == ("multi-species",)
    assert derived.root_type == "crown"


# --------------------------------------------------------------------------------------
# update-inventory-derivation — Capture Mode Derivation (#65)
# --------------------------------------------------------------------------------------


def test_the_one_plant_count_token_is_recognised():
    """#65's reproduction: `multiplant_cylinder/` derived `cylinder`."""
    joined = gap.derive(
        _family("SLEAP_arabidopsis/multiplant_cylinder/primary/labels.v001.slp")
    )
    alone = gap.derive(_family("SLEAP_arabidopsis/multiplant/primary/labels.v001.slp"))

    assert joined.mode == "multiplant cylinder"
    assert alone.mode == "multiplant cylinder"
    assert "ambiguous-mode" not in joined.flags
    assert "ambiguous-mode" not in alone.flags


def test_a_capture_word_apart_from_the_count_token_is_part_of_it():
    derived = gap.derive(
        _family("SLEAP_arabidopsis/cyl_primary/multiplant/labels.v001.slp")
    )

    assert derived.mode == "multiplant cylinder"
    assert "ambiguous-mode" not in derived.flags


def test_look_alike_spellings_are_not_recognised():
    """Characterisation: `multi`, `multiclass` and `multiple` all mean something else."""
    assert (
        gap.derive(_family("SLEAP_Soy/primary_multi-day/labels.v001.slp")).mode is None
    )
    assert (
        gap.derive(
            _family("SLEAP_medicago_plates/multiclass_bottomup/labels.v001.slp")
        ).mode
        == "plate"
    )
    assert (
        gap.derive(_family("SLEAP_multiple_species/cyl/labels.v001.slp")).mode
        == "cylinder"
    )


def test_two_capture_words_derive_nothing():
    """The first token used to win silently."""
    plain = gap.derive(_family("plates/cyl_primary/labels.v001.slp"))
    counted = gap.derive(_family("multiplant/plate/labels.v001.slp"))

    assert plain.mode is None
    assert counted.mode is None
    assert plain.modes_named == ("cylinder", "plate")
    assert counted.modes_named == ("multiplant cylinder", "plate")
    assert "ambiguous-mode" in plain.flags
    assert "ambiguous-mode" in counted.flags


def test_a_capture_word_named_twice_is_one():
    """Characterisation."""
    derived = gap.derive(
        _family("SLEAP_arabidopsis_plates/plate_primary/labels.v001.slp")
    )

    assert derived.mode == "plate"
    assert derived.flags == ()


def test_flags_are_sorted():
    derived = gap.derive(
        _family("SLEAP_arabidopsis_plates/plates/cyl_x/labels_wheat_2-3DAG.v001.slp")
    )

    assert derived.mode is None
    assert derived.flags == ("ambiguous-mode", "folder-species-differs")


def test_the_derived_spelling_is_the_contracts():
    """Characterisation: the derived mode is a `MODE_VOCAB` value."""
    from sleap_roots_training.registry import chooser

    assert "multiplant cylinder" in chooser.MODE_VOCAB


# --------------------------------------------------------------------------------------
# update-inventory-derivation — Skeleton Table Mode Gap, names that say too much
# --------------------------------------------------------------------------------------


def test_a_name_that_says_too_much_is_skipped_by_its_own_reason(tmp_path):
    """Each family derives everything except the one field its name over-specifies."""
    pooled = write_labels(
        tmp_path / "cyl_x" / "primary_x" / "labels_canola_pennycress.v001.slp",
        node_names=_nodes(6),
    )
    two_modes = write_labels(
        tmp_path / "SLEAP_arabidopsis" / "plates" / "cyl_primary" / "labels.v001.slp",
        node_names=_nodes(6),
    )

    report = gap.build_report([_observe(pooled), _observe(two_modes)], table=())

    assert report.families_skipped_reasons == {
        "multi-species": 1,
        "ambiguous-mode": 1,
    }


def test_a_crowded_capture_family_is_a_gap_not_a_match(tmp_path):
    """Characterisation after 2.2: a multiplant family is no longer a cylinder match."""
    table = (_row("arabidopsis", "cylinder", "primary", 6),)
    path = write_labels(
        tmp_path / "multiplant_cylinder" / "arabidopsis_primary" / "labels.v001.slp",
        node_names=_nodes(6),
    )

    report = gap.build_report([_observe(path)], table=table)

    assert len(report.mode_gaps) == 1
    assert report.mode_gaps[0].mode == "multiplant cylinder"
    assert report.mode_gaps[0].table_modes == ("cylinder",)
    assert report.node_count_disagreements == []


def test_pooled_names_still_count_as_uncovered(tmp_path):
    """A pooled file is labels of each crop it names."""
    table = (_row("soybean", "cylinder", "primary", 6),)
    by_filename = write_labels(
        tmp_path / "cyl_x" / "primary_x" / "labels_canola_pennycress.v001.slp",
        node_names=_nodes(6),
    )
    by_folder = write_labels(
        tmp_path
        / "SLEAP_Canola_Pennycress"
        / "cyl_x"
        / "primary_x"
        / "labels.v001.slp",
        node_names=_nodes(6),
    )

    report = gap.build_report([_observe(by_filename), _observe(by_folder)], table=table)

    assert "pennycress" in report.uncovered_species
    assert report.families_skipped_reasons["multi-species"] == 2
