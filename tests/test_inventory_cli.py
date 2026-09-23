"""The ``inventory labels`` command.

Placed after ``seed-registry`` and before ``validate`` in ``cli.py``, clear of all four
of PR #48's hunks.
"""

from __future__ import annotations

from click.testing import CliRunner

from inventory_fixtures import build_share_tree
from sleap_roots_training.cli import main
from wandb.sdk.artifacts.artifact_manifest_entry import ArtifactManifestEntry

from sleap_roots_training.inventory import emit, verify

# The family's *latest* member, since that is the one a scan reads and digests.
REAL = ("SLEAP_soybean/primary_6nodes/labels.v002.slp",)


def test_the_command_writes_both_artifacts_and_exits_zero(tmp_path):
    """Scenario: Exit status reflects usability, not findings."""
    root = build_share_tree(tmp_path / "share", real=REAL)
    out = tmp_path / "inventory"

    result = CliRunner().invoke(
        main, ["inventory", "labels", str(root), "--output", str(out), "--no-registry"]
    )

    assert result.exit_code == 0, result.output
    assert (out / emit.TABLE_FILENAME).is_file()
    assert (out / emit.REPORT_FILENAME).is_file()
    assert "famil" in result.output


def test_a_missing_root_exits_non_zero_and_writes_nothing(tmp_path):
    """The other half: only an unusable root is an error."""
    out = tmp_path / "inventory"

    result = CliRunner().invoke(
        main,
        [
            "inventory",
            "labels",
            str(tmp_path / "nope"),
            "--output",
            str(out),
            "--no-registry",
        ],
    )

    assert result.exit_code != 0
    assert not out.exists()


def test_the_command_reports_directories_it_will_not_resolve(tmp_path):
    """The human stop, surfaced at the terminal and not only in the report."""
    root = build_share_tree(tmp_path / "share", real=REAL)

    result = CliRunner().invoke(
        main,
        [
            "inventory",
            "labels",
            str(root),
            "--output",
            str(tmp_path / "out"),
            "--no-registry",
        ],
    )

    assert "no determination made" in result.output


def test_no_emitted_path_escapes_the_root(tmp_path):
    """The whole point of the whitelist, asserted end to end.

    The root here is nested under a directory named for a person, exactly as the real
    share is. Nothing above the root may appear in either artifact.
    """
    root = build_share_tree(tmp_path / "users" / "colleague" / "SLEAP", real=REAL)
    out = tmp_path / "inventory"

    CliRunner().invoke(
        main, ["inventory", "labels", str(root), "--output", str(out), "--no-registry"]
    )

    for name in (emit.TABLE_FILENAME, emit.REPORT_FILENAME):
        text = (out / name).read_text(encoding="utf-8")
        assert "colleague" not in text
        assert str(tmp_path) not in text


def test_the_group_is_listed_in_help():
    """A new command group nobody can find is not shipped."""
    result = CliRunner().invoke(main, ["--help"])
    assert "inventory" in result.output


def test_an_unreachable_registry_warns_and_keeps_going(tmp_path, monkeypatch):
    """Not fatal, and not silent either.

    `not-checked` is a different finding from `unregistered`: not looking is not the
    same as looking and finding nothing, and the file-derived evidence is unaffected.
    """
    root = build_share_tree(tmp_path / "share", real=REAL)
    out = tmp_path / "inventory"

    def _unreachable(*_args, **_kwargs):
        raise RuntimeError("could not read the labels registry: no credential")

    monkeypatch.setattr(verify, "fetch_index", _unreachable)
    result = CliRunner().invoke(
        main, ["inventory", "labels", str(root), "--output", str(out)]
    )

    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output
    assert "not-checked" in result.output
    assert emit.NOT_CHECKED in (out / emit.TABLE_FILENAME).read_text(encoding="utf-8")


def test_a_reachable_registry_fills_the_status_column(tmp_path, monkeypatch):
    """Scenario: A digest match is reported as verified, end to end."""
    root = build_share_tree(tmp_path / "share", real=REAL)
    out = tmp_path / "inventory"
    scanned = root / REAL[0]

    entry = ArtifactManifestEntry(
        path=scanned.name, digest=verify.content_digest(scanned), size=1
    )
    monkeypatch.setattr(verify, "fetch_index", lambda *a, **k: {scanned.name: [entry]})

    result = CliRunner().invoke(
        main, ["inventory", "labels", str(root), "--output", str(out)]
    )

    assert result.exit_code == 0, result.output
    table = (out / emit.TABLE_FILENAME).read_text(encoding="utf-8")
    assert verify.VERIFIED in table
    assert verify.UNREGISTERED in table
