"""Deterministic artifacts, and the human stop.

Covers ``Requirement: Deterministic Artifacts`` and ``Requirement: No Decision
Capture``. The artifacts have to diff across runs, which means no wall-clock anything in
them, and the tool has to say what it cannot determine rather than deciding it.
"""

from __future__ import annotations

import csv
import json

import pytest
import wandb

from inventory_fixtures import build_share_tree, write_labels
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


def test_uncovered_tokens_that_are_not_crops_are_separated(tmp_path):
    """Derivation is open, so directory names that are not crops land in the list too.

    The real share yields `packages`, `shoots` and `cropping` alongside wheat and
    sorghum. Filtering them out would hide a genuinely new crop, which is the finding
    this report exists to make — so they are separated and labelled instead.
    """
    root = tmp_path / "share"
    write_labels(root / "SLEAP_wheat" / "seminal" / "labels.v001.slp")
    write_labels(root / "SLEAP_packages" / "primary" / "labels.v001.slp")

    out = tmp_path / "inventory"
    emit.write(emit.build(root), out)
    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")

    assert "- wheat" in report
    assert "not** species" in report
    assert "packages" in report.split("not** species")[1]


def test_a_crowded_directory_is_truncated_with_a_count(share, tmp_path):
    """One measured directory holds 30 families; the untruncated line is unreadable."""
    inventory = emit.build(share)
    crowded = emit.AmbiguousDirectory(
        path="<ROOT>/experiments/output",
        family_count=30,
        stems=tuple(f"family_{i:02d}" for i in range(30)),
    )
    inventory.ambiguous_directories = [crowded]

    out = tmp_path / "inventory"
    emit.write(inventory, out)
    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")

    assert "holds 30 families" in report
    assert "and 22 more" in report
    assert "family_29" not in report


# --------------------------------------------------------------------------------------
# Regressions from the PR #58 review.
# --------------------------------------------------------------------------------------


def _rows(out):
    with (out / emit.TABLE_FILENAME).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t"])
def test_a_formula_named_skeleton_cannot_execute_in_a_spreadsheet(tmp_path, prefix):
    """These artifacts are committed and opened in Excel.

    `csv` quotes correctly for parsers, but Excel strips the quotes and evaluates a cell
    beginning `=`, `+`, `-`, `@` or a tab. The strings come from files written on other
    machines, so they are attacker-influenced in the only sense that matters here.
    """
    root = tmp_path / "share"
    write_labels(
        root / "SLEAP_soybean" / "primary" / "labels.v001.slp",
        skeleton_names=(f'{prefix}HYPERLINK("http://evil","x")',),
    )
    out = tmp_path / "inventory"
    emit.write(emit.build(root), out)

    for row in _rows(out):
        for value in row.values():
            assert not value.startswith(("=", "+", "-", "@", "\t", "\r"))


def test_video_filenames_round_trip_when_a_filename_contains_spaces(tmp_path):
    """Space-joining produced 8,489 fragment tokens in the first committed scan.

    `GSOR 301503 RDP2-3 +F.h5` came out as four tokens, so the machine-readable output
    of an enumeration tool could not be read back.
    """
    root = tmp_path / "share"
    images = tmp_path / "imgs"
    write_labels(
        root / "SLEAP_rice" / "primary" / "labels.v001.slp",
        n_frames=2,
        image_dir=images,
    )
    for old, new in zip(
        sorted(images.glob("*.jpg")), ("GSOR 301503 +F.jpg", "b c.jpg")
    ):
        old.rename(images / new)
    # Re-write the project so the recorded paths carry the spaces.
    write_labels(
        root / "SLEAP_rice" / "primary" / "labels.v002.slp",
        n_frames=2,
        image_dir=tmp_path / "spaced",
    )

    out = tmp_path / "inventory"
    emit.write(emit.build(root), out)
    for row in _rows(out):
        assert json.loads(row["video_filenames"]) == sorted(
            json.loads(row["video_filenames"])
        )


def test_an_error_message_never_carries_an_absolute_path(tmp_path, monkeypatch):
    """`str(error)` went into the CSV verbatim, bypassing redaction entirely.

    The first scan was clean only because its two failures produced path-free h5py
    messages; a dropped SMB session mid-scan writes the share path into a committed
    file. The failure is injected rather than provoked so the test cannot pass by luck.
    """
    directory = tmp_path / "share" / "SLEAP_wheat" / "seminal"
    write_labels(directory / "labels.v001.slp")

    def _boom(*_args, **_kwargs):
        raise OSError(
            "[Errno 2] Unable to open file (name = "
            r"'Z:\users\eberrigan\SLEAP\SLEAP_wheat\labels.v001.slp')"
        )

    monkeypatch.setattr(emit.read.sio, "load_slp", _boom)

    out = tmp_path / "inventory"
    emit.write(emit.build(tmp_path / "share"), out)

    errors = [r["error"] for r in _rows(out) if r["error"]]
    assert errors
    for message in errors:
        assert "eberrigan" not in message
        assert "Z:" not in message
        assert "\\" not in message


def test_every_family_member_is_named_in_the_row(tmp_path):
    """A family emits one row, so the non-latest members must still be reachable."""
    directory = tmp_path / "share" / "SLEAP_rice" / "primary"
    for name in ("labels.v001.slp", "labels.v002.slp", "labels.v003.slp"):
        write_labels(directory / name)

    out = tmp_path / "inventory"
    emit.write(emit.build(tmp_path / "share"), out)
    row = _rows(out)[0]

    assert row["members"] == "3"
    assert json.loads(row["member_filenames"]) == [
        "labels.v001.slp",
        "labels.v002.slp",
        "labels.v003.slp",
    ]


def test_a_packaged_twin_is_cross_referenced_in_the_table(tmp_path):
    """Spec clause: the report cross-references them as one effort in two forms.

    `Family.twins` was computed and read by nothing, so 47 twin pairs on the real corpus
    were emitted as unrelated rows and anyone summing `frames` double-counted.
    """
    directory = tmp_path / "share" / "SLEAP_soybean" / "primary"
    write_labels(directory / "labels.v003.slp")
    write_labels(directory / "labels.v003.pkg.slp")

    out = tmp_path / "inventory"
    emit.write(emit.build(tmp_path / "share"), out)
    rows = {r["path"].rsplit("/", 1)[-1]: r for r in _rows(out)}

    assert rows["labels.v003.slp"]["twin_of"] == "labels.v003.pkg.slp"
    assert rows["labels.v003.pkg.slp"]["twin_of"] == "labels.v003.slp"


def test_a_partial_scan_refuses_to_overwrite_the_artifacts(tmp_path, monkeypatch):
    """A root that exists but cannot be listed truncated the committed CSV to a header.

    `chmod 0o000` still passes `is_dir()`, so the scan found nothing, wrote a bare
    header and exited 0 — and the diff read as "1,250 labelings disappeared".
    """
    root = tmp_path / "share"
    root.mkdir()

    real_walk = emit.discover.walk

    def _blind(path):
        result = real_walk(path)
        result.unreadable_paths.append(path)
        return result

    monkeypatch.setattr(emit.discover, "walk", _blind)

    with pytest.raises(emit.PartialScan):
        emit.build(root)


def test_a_mismatch_names_both_digests_in_the_table(tmp_path):
    """Scenario: a mismatch is "reported as mismatching, naming both digests"."""
    from sleap_roots_training.inventory import verify

    root = tmp_path / "share"
    path = write_labels(root / "SLEAP_rice" / "primary" / "labels.v001.slp")
    verdict = verify.Verification(
        status=verify.MISMATCH,
        local_digest="LOCAL==",
        recorded_digests=("RECORDED==",),
        matches=1,
    )

    out = tmp_path / "inventory"
    emit.write(emit.build(root, verifier=lambda paths: {path: verdict}), out)
    row = _rows(out)[0]

    assert row["registry_status"] == verify.MISMATCH
    assert "LOCAL==" in row["registry_detail"]
    assert "RECORDED==" in row["registry_detail"]


def test_the_report_publishes_its_own_denominator(tmp_path):
    """The first committed report gave a finding over 3.8% of the corpus and said so
    nowhere."""
    root = tmp_path / "share"
    write_labels(
        root / "cyl_arabidopsis_primary_6nodes" / "labels.v001.slp",
        skeleton_names=("arabidopsis_primary",),
    )
    write_labels(
        root / "unknowable" / "labels.v001.slp", skeleton_names=("Skeleton-1",)
    )

    out = tmp_path / "inventory"
    emit.write(emit.build(root), out)
    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")

    assert "Analysed 1 of 2 families" in report
    assert "not analysed:" in report


def test_every_candidate_is_read_not_just_the_latest(tmp_path):
    """Requirement 3 says "read **each** candidate"; 197 were never opened.

    A family emits one row, but a member that disagrees with the latest has to surface —
    otherwise mixed node counts inside a family are structurally undetectable.
    """
    directory = tmp_path / "share" / "SLEAP_soybean" / "primary_6nodes"
    write_labels(directory / "labels.v001.slp", node_names=("r1", "r2", "r3"))
    write_labels(directory / "labels.v002.slp", node_names=("r1", "r2"))

    out = tmp_path / "inventory"
    emit.write(emit.build(tmp_path / "share"), out)
    row = _rows(out)[0]

    assert row["members"] == "2"
    assert row["member_node_counts"] == json.dumps([3, 2])
    assert row["members_disagree"] == "node_count"


def test_the_mode_gap_sections_are_rendered(tmp_path):
    """Scenario: The findings are rendered, asserted against the report bytes.

    The headline finding's report block was once at 0% coverage; the report is what a
    reader sees, so each finding is checked there rather than only in the dataclass.
    """
    from sleap_roots_training.labeling.skeletons import SkeletonRow

    table = (
        SkeletonRow(
            species="arabidopsis",
            mode="cylinder",
            root_type="lateral",
            age=None,
            node_count=4,
        ),
        SkeletonRow(
            species="arabidopsis",
            mode="plate",
            root_type="primary",
            age="2, 3, 4, 5, 6, 7",
            node_count=8,
        ),
    )
    root = tmp_path / "share"
    write_labels(
        root / "plate_arabidopsis_lateral_3nodes" / "labels.v001.slp",
        skeleton_names=("Skeleton-1",),
        node_names=tuple(f"r{i}" for i in range(1, 4)),
    )
    write_labels(
        root / "plate_arabidopsis_primary_8nodes" / "labels.v001.slp",
        skeleton_names=("Skeleton-1",),
        node_names=tuple(f"r{i}" for i in range(1, 8)),
    )

    out = tmp_path / "inventory"
    emit.write(emit.build(root, table=table), out)
    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")

    assert "Rows selected by more than one capture mode" not in report
    assert "### Capture modes with no row" in report
    assert "`(arabidopsis, plate, lateral)`" in report
    assert "only in cylinder" in report
    assert "### Node counts that disagree with their row" in report
    assert "`(arabidopsis, plate, primary)`" in report
    assert "row says 8" in report
    assert "observed 7" in report


def test_the_unparseable_section_is_deduplicated_and_path_qualified(tmp_path):
    """1,235 bullets over 364 basenames, `labels_gt.train.slp` 63 times identically.

    Rendered from an unredacted absolute path via `Path(...).name`, which also means the
    one renderer that bypasses redaction entirely.
    """
    root = tmp_path / "share"
    for crop in ("SLEAP_sorghum", "SLEAP_rice"):
        write_labels(
            root / crop / "primary" / "labels.v001.slp",
            skeleton_names=("Skeleton-1",),
        )

    out = tmp_path / "inventory"
    emit.write(emit.build(root), out)
    report = (out / emit.REPORT_FILENAME).read_text(encoding="utf-8")

    section = report.split("### Skeleton names the existing check cannot resolve")[1]
    assert section.count("labels.v001.slp") == 2
    assert "<ROOT>/SLEAP_sorghum/primary/labels.v001.slp" in section
    assert str(tmp_path) not in report
