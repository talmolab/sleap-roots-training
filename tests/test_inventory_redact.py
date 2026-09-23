r"""Path emission, by whitelist.

Covers ``Requirement: Path Redaction``. Nothing above the supplied discovery root is
emitted, and a referenced video path is emitted as its filename alone. That is a
whitelist: it removes the class rather than enumerating the ways a name can hide in a
string.

The blacklist it replaced leaked on the two real paths it was written for. The markers
were slash-terminated (``users/``, ``Users/``, ``home/``) and Windows SLEAP records video
paths with **backslashes**, so both colleagues' names passed straight through. Relative
and ``..``-rooted paths leaked, ``pathlib`` folds ``\\\\server\\share`` into the anchor so
a person-named share survived, and ``home/`` matched inside words like ``genome``. These
tests keep all of those closed.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from sleap_roots_training.inventory import redact

# --------------------------------------------------------------------------------------
# Candidate paths — emitted relative to the root
# --------------------------------------------------------------------------------------


def test_a_candidate_path_is_emitted_relative_to_the_root(tmp_path):
    """Scenario: A candidate path is emitted relative to the root."""
    root = tmp_path / "users" / "someone" / "SLEAP"
    candidate = root / "SLEAP_soybean" / "primary_6nodes" / "labels.v001.slp"
    candidate.parent.mkdir(parents=True)
    candidate.touch()

    emitted = redact.emit_path(candidate, root)

    assert emitted.text.startswith(redact.ROOT_TOKEN)
    assert (
        emitted.text
        == f"{redact.ROOT_TOKEN}/SLEAP_soybean/primary_6nodes/labels.v001.slp"
    )
    assert not emitted.outside_root


def test_no_segment_of_the_root_survives_into_an_emitted_path(tmp_path):
    """The owner's own directory names are above the root, so they never appear."""
    root = tmp_path / "users" / "eberrigan" / "SLEAP"
    candidate = root / "SLEAP_wheat" / "seminal" / "labels.v004.slp"
    candidate.parent.mkdir(parents=True)
    candidate.touch()

    text = redact.emit_path(candidate, root).text

    # Component-wise, not substring: `SLEAP_wheat` legitimately contains the root's own
    # final segment `SLEAP`, and that is not a leak. What must never appear is one of
    # the root's directories *as a component* — `eberrigan` above all.
    emitted_components = set(text.split("/"))
    assert emitted_components & set(root.parts) == set()
    assert "eberrigan" not in text


# --------------------------------------------------------------------------------------
# Referenced video paths — emitted as a filename alone
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "recorded",
    [
        r"C:\Users\colleague\OneDrive - Salk Institute\exp\scan_001.jpg",
        "C:/Users/colleague/OneDrive - Salk Institute/exp/scan_001.jpg",
        r"Z:\colleague\experiments\scan_001.jpg",
        "Z:/colleague/experiments/scan_001.jpg",
        r"\\multilab-na.ad.salk.edu\users\colleague\SLEAP\scan_001.jpg",
        "//nas01/colleague/experiments/scan_001.jpg",
        "/home/colleague/experiments/scan_001.jpg",
        r"..\colleague\exp\scan_001.jpg",
        "~colleague/exp/scan_001.jpg",
        "colleague/exp/scan_001.jpg",
    ],
)
def test_a_referenced_video_path_is_emitted_as_a_filename(recorded):
    """Scenario: A referenced video path is emitted as a filename.

    Every shape here defeated at least one rule of the blacklist this replaced. The
    backslash forms are the ones that matter most: that is what Windows SLEAP records,
    whatever host later runs the scan.
    """
    emitted = redact.emit_video_path(recorded)

    assert emitted == "scan_001.jpg"
    assert "colleague" not in emitted
    assert "salk" not in emitted.lower()


def test_both_separators_are_split_on_every_platform():
    """`PurePath` is `PurePosixPath` on the Ubuntu and macOS runners.

    There, ``Z:/a/b`` has ``drive=''`` and ``parts[0] == 'Z:'``, so a first-segment rule
    would redact the drive letter and emit the name. Splitting on both separators
    explicitly is what makes this behave identically on all three runners.
    """
    assert PureWindowsPath(r"Z:\a\name.jpg").name == "name.jpg"
    assert PurePosixPath(r"Z:\a\name.jpg").name == r"Z:\a\name.jpg"

    assert redact.emit_video_path(r"Z:\a\name.jpg") == "name.jpg"
    assert redact.emit_video_path("Z:/a/name.jpg") == "name.jpg"


def test_an_unusable_recorded_path_emits_a_placeholder_not_the_original():
    """A string with no filename must not fall through to itself."""
    for odd in ("", "   ", "/", "\\", r"C:\\"):
        assert redact.emit_video_path(odd) == redact.UNKNOWN_FILENAME


# --------------------------------------------------------------------------------------
# Outside the root
# --------------------------------------------------------------------------------------


def test_a_candidate_outside_the_root_is_reported_by_filename(tmp_path):
    """Scenario: A candidate outside the root is reported by filename."""
    root = tmp_path / "share"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "colleague" / "labels.v001.slp"
    outside.parent.mkdir(parents=True)
    outside.touch()

    emitted = redact.emit_path(outside, root)

    assert emitted.outside_root
    assert emitted.text == "labels.v001.slp"
    assert "colleague" not in emitted.text
    assert emitted.reason == redact.OUTSIDE_ROOT


def test_a_dotdot_path_that_escapes_the_root_is_outside_it(tmp_path):
    """`..` defeated the old first-segment rule by being the first segment."""
    root = tmp_path / "share"
    (root / "inner").mkdir(parents=True)
    escaping = root / "inner" / ".." / ".." / "colleague" / "labels.v001.slp"

    emitted = redact.emit_path(escaping, root)

    assert emitted.outside_root
    assert "colleague" not in emitted.text


# --------------------------------------------------------------------------------------
# What is not a path
# --------------------------------------------------------------------------------------


def test_non_path_fields_survive_untouched():
    """`genotype`, `accession_id` and `experiment_name` are not person-identifying."""
    row = {
        "genotype": "Williams-82",
        "accession_id": "PI-548631",
        "experiment_name": "weep-2026",
    }
    assert redact.emit_fields(row) == row
