"""The ``inventory labels`` command.

Placed after ``seed-registry`` and before ``validate`` in ``cli.py``, clear of all four
of PR #48's hunks.
"""

from __future__ import annotations

from click.testing import CliRunner

from inventory_fixtures import build_share_tree
from sleap_roots_training.cli import main
from sleap_roots_training.inventory import emit

REAL = ("SLEAP_soybean/primary_6nodes/labels.v001.slp",)


def test_the_command_writes_both_artifacts_and_exits_zero(tmp_path):
    """Scenario: Exit status reflects usability, not findings."""
    root = build_share_tree(tmp_path / "share", real=REAL)
    out = tmp_path / "inventory"

    result = CliRunner().invoke(
        main, ["inventory", "labels", str(root), "--output", str(out)]
    )

    assert result.exit_code == 0, result.output
    assert (out / emit.TABLE_FILENAME).is_file()
    assert (out / emit.REPORT_FILENAME).is_file()
    assert "famil" in result.output


def test_a_missing_root_exits_non_zero_and_writes_nothing(tmp_path):
    """The other half: only an unusable root is an error."""
    out = tmp_path / "inventory"

    result = CliRunner().invoke(
        main, ["inventory", "labels", str(tmp_path / "nope"), "--output", str(out)]
    )

    assert result.exit_code != 0
    assert not out.exists()


def test_the_command_reports_directories_it_will_not_resolve(tmp_path):
    """The human stop, surfaced at the terminal and not only in the report."""
    root = build_share_tree(tmp_path / "share", real=REAL)

    result = CliRunner().invoke(
        main, ["inventory", "labels", str(root), "--output", str(tmp_path / "out")]
    )

    assert "no determination made" in result.output


def test_no_emitted_path_escapes_the_root(tmp_path):
    """The whole point of the whitelist, asserted end to end.

    The root here is nested under a directory named for a person, exactly as the real
    share is. Nothing above the root may appear in either artifact.
    """
    root = build_share_tree(tmp_path / "users" / "colleague" / "SLEAP", real=REAL)
    out = tmp_path / "inventory"

    CliRunner().invoke(main, ["inventory", "labels", str(root), "--output", str(out)])

    for name in (emit.TABLE_FILENAME, emit.REPORT_FILENAME):
        text = (out / name).read_text(encoding="utf-8")
        assert "colleague" not in text
        assert str(tmp_path) not in text


def test_the_group_is_listed_in_help():
    """A new command group nobody can find is not shipped."""
    result = CliRunner().invoke(main, ["--help"])
    assert "inventory" in result.output
