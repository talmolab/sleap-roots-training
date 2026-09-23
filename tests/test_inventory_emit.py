"""Deterministic artifacts, and the human stop.

Covers ``Requirement: Deterministic Artifacts`` and ``Requirement: No Decision
Capture``. The artifacts have to diff across runs, which means no wall-clock anything in
them, and the tool has to say what it cannot determine rather than deciding it.
"""

from __future__ import annotations

import csv

import pytest
import wandb

from inventory_fixtures import build_share_tree
from sleap_roots_training.inventory import emit

REAL = (
    "SLEAP_soybean/primary_6nodes/labels.v001.slp",
    "SLEAP_soybean/primary_6nodes/labels.v002.slp",
    "SLEAP_rice/primary_6nodes/labels.v001.slp",
    "SLEAP_medicago_plates/combined_roots/MK24_roots.slp",
)


@pytest.fixture
def share(tmp_path):
    """A share tree whose candidates are real, readable projects."""
    return build_share_tree(tmp_path / "share", real=REAL)


def test_two_runs_over_an_unchanged_tree_agree(share, tmp_path, monkeypatch):
    """Scenario: Two runs over an unchanged tree agree.

    Byte-identical, not merely equivalent. The registry side is stubbed so identity does
    not depend on live state, and `wandb.Api` is barred outright so a stray read-back
    cannot make the run non-hermetic.
    """

    def _no_api(*_args, **_kwargs):
        raise AssertionError("emission must not construct a wandb.Api")

    monkeypatch.setattr(wandb, "Api", _no_api)

    first = tmp_path / "run1"
    second = tmp_path / "run2"
    emit.write(emit.build(share), first)
    emit.write(emit.build(share), second)

    for name in (emit.TABLE_FILENAME, emit.REPORT_FILENAME):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_the_artifacts_carry_no_run_varying_metadata(share, tmp_path):
    """A `generated at` line is the single most likely way to break the above."""
    out = tmp_path / "inventory"
    emit.write(emit.build(share), out)
    text = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8").lower()

    for forbidden in ("generated", "timestamp", "elapsed", "duration", "hostname"):
        assert forbidden not in text


def test_rows_are_ordered_by_emitted_path(share, tmp_path):
    """Scenario: Rows are ordered by emitted path."""
    out = tmp_path / "inventory"
    emit.write(emit.build(share), out)

    with (out / emit.TABLE_FILENAME).open(encoding="utf-8", newline="") as handle:
        paths = [row["path"] for row in csv.DictReader(handle)]

    assert paths == sorted(paths)
    assert paths and all(p.startswith(emit.redact.ROOT_TOKEN) for p in paths)


def test_the_only_files_written_are_the_table_and_the_report(share, tmp_path):
    """Scenario: Only labels files, the skeleton table and manifests are read."""
    out = tmp_path / "inventory"
    emit.write(emit.build(share), out)
    assert sorted(p.name for p in out.iterdir()) == sorted(
        [emit.TABLE_FILENAME, emit.REPORT_FILENAME]
    )

    emit.write(emit.build(share), out)
    assert len(list(out.iterdir())) == 2


def test_the_module_grows_no_decision_capture_surface():
    """Guards the governing principle against regrowth.

    The previous attempt grew a decision file, an identifier scheme, merge semantics and
    verdict forms, all to avoid asking a person. This fails if any of that comes back.
    """
    forbidden = ("decision", "verdict", "adjudicat", "promote", "override")
    names = [n.lower() for n in dir(emit)]
    assert not [n for n in names if any(word in n for word in forbidden)]


def test_an_unresolvable_group_is_listed_not_resolved(share, tmp_path):
    """Scenario: An unresolvable group is listed, not resolved.

    A directory is not a collection: one measured directory holds 28 labels files
    spanning a sorghum superset, a soybean collection, a generalist, per-labeler inputs
    and practice files.
    """
    inventory = emit.build(share)
    out = tmp_path / "inventory"
    emit.write(inventory, out)
    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")

    assert inventory.ambiguous_directories
    crowded = inventory.ambiguous_directories[0]
    assert crowded.family_count > 1
    assert "makes no determination" in report
    assert crowded.path in report
    assert "A directory is not a collection." in report


def test_a_name_derived_species_is_labelled_and_called_not_evidence(share, tmp_path):
    """Scenario: A name-derived species is labelled as name-derived."""
    out = tmp_path / "inventory"
    emit.write(emit.build(share), out)

    with (out / emit.TABLE_FILENAME).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert {r["species_source"] for r in rows} == {"name-derived"}
    assert "soybean" in {r["species"] for r in rows}

    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")
    assert "not evidence" in report


def test_a_scan_with_findings_still_exits_zero(share):
    """Scenario: Exit status reflects usability, not findings."""
    inventory = emit.build(share)
    assert inventory.gap.uncovered_species or inventory.gap.unparseable_skeletons
    assert emit.exit_code(inventory) == 0


def test_a_missing_or_unreadable_root_is_refused(tmp_path):
    """The other half of the same scenario: non-zero, and no partial table."""
    out = tmp_path / "inventory"
    with pytest.raises(emit.UnusableRoot):
        emit.build(tmp_path / "does-not-exist")
    assert not out.exists()
