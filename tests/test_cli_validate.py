"""Tests for the ``sleap-roots-training validate`` CLI subcommand.

Uses Click's ``CliRunner`` (the repo's CLI-test pattern) to assert the exit-code contract:
0 on a conforming config, non-zero with a clear field-named message otherwise, and a clean
message (not a traceback) on malformed input.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from sleap_roots_training import cli, config


@pytest.fixture(autouse=True)
def _force_base_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the no-``[train]`` path so the CLI tests are deterministic on any host."""
    monkeypatch.setattr(config, "_deep_validation_available", lambda: False)


def _invoke(args):
    return CliRunner().invoke(cli.main, args)


def test_validate_good_config_exits_zero(write_config):
    result = _invoke(["validate", str(write_config())])
    assert result.exit_code == 0, result.output
    assert "ok:" in result.output.lower()
    # base-safe path (autouse) says deep validation was skipped rather than "valid".
    assert "skipped" in result.output.lower()


def test_validate_invalid_metadata_exits_nonzero(write_config):
    path = write_config(overrides={"experiment": {"species": "banana"}})
    result = _invoke(["validate", str(path)])
    assert result.exit_code != 0
    assert "species" in result.output


def test_validate_missing_seed_exits_nonzero(write_config):
    path = write_config(drop=("trainer_config.seed",))
    result = _invoke(["validate", str(path)])
    assert result.exit_code != 0
    assert "seed" in result.output


def test_validate_malformed_yaml_exits_nonzero_without_traceback(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("experiment: [unbalanced\n", encoding="utf-8")
    result = _invoke(["validate", str(path)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_validate_nonexistent_path_exits_nonzero(tmp_path):
    result = _invoke(["validate", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0


def test_validate_reports_skip_note_without_train_extra(write_config, monkeypatch):
    # Force the base-safe path so this is deterministic even where [train] is installed.
    monkeypatch.setattr(config, "_deep_validation_available", lambda: False)
    result = _invoke(["validate", str(write_config())])
    assert result.exit_code == 0, result.output
    assert "train" in result.output.lower()


def test_emit_strips_experiment_to_stdout(write_config):
    result = _invoke(["emit", str(write_config())])
    assert result.exit_code == 0, result.output
    assert "experiment" not in result.output
    assert "data_config" in result.output


def test_emit_writes_output_file(write_config, tmp_path):
    out = tmp_path / "resolved.yaml"
    result = _invoke(["emit", str(write_config()), "-o", str(out)])
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "experiment" not in text
    assert "data_config" in text


def test_emit_invalid_config_exits_nonzero(write_config):
    path = write_config(drop=("trainer_config.seed",))
    result = _invoke(["emit", str(path)])
    assert result.exit_code != 0
    assert "seed" in result.output


def test_emit_to_missing_dir_errors_cleanly(write_config, tmp_path):
    out = tmp_path / "does_not_exist" / "resolved.yaml"  # parent dir absent
    result = _invoke(["emit", str(write_config()), "-o", str(out)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
