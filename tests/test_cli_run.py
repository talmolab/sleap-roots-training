"""Tests for the ``sleap-roots-training run`` subcommand.

Base-install safe: the backend is never installed in CI, so ``resolve_sleap_nn`` and the
``subprocess.Popen`` call are replaced. What is asserted here is the *contract* -- the
step order, what reaches the subprocess, and what is on disk when each step fails.

Every test sandboxes the checkpoint tree. ``conftest.VALID_CONFIG`` ships a **relative**
``ckpt_dir: models`` and ``CliRunner`` does not change directory, so an unmodified
``write_config()`` would write into the repo checkout -- where ``.gitignore``'s ``/models/``
would hide it, and where "nothing was written" would quietly stop meaning anything.
"""

from __future__ import annotations

import ast
import importlib.machinery
import sys
import types
from pathlib import Path

import pytest
from click.testing import CliRunner

from sleap_roots_training import backend, cli, config


class _Recorder:
    """Stands in for ``subprocess.Popen``, recording every launch."""

    calls: list = []
    statuses: list = [0]

    def __init__(self, argv, **kwargs):
        self.argv = argv
        type(self).calls.append((argv, kwargs))
        self._statuses = list(type(self).statuses)

    def wait(self):
        status = self._statuses.pop(0)
        if isinstance(status, BaseException):
            raise status
        return status

    def kill(self):  # pragma: no cover - a failure of the interrupt contract
        raise AssertionError("run must not kill the backend")


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    """Run inside tmp_path and force the base-safe validation path."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_deep_validation_available", lambda: False)


@pytest.fixture
def backend_stub(monkeypatch, tmp_path):
    """Resolve to a fake console script and record subprocess launches."""
    binary = tmp_path / "bin" / "sleap-nn"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(backend, "resolve_sleap_nn", lambda: binary)
    _Recorder.calls = []
    _Recorder.statuses = [0]
    monkeypatch.setattr(backend.subprocess, "Popen", _Recorder)
    return _Recorder


@pytest.fixture
def run_config(write_config, tmp_path):
    """A valid config whose checkpoint tree lives inside tmp_path."""

    def _make(**overrides):
        trainer = {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        trainer.update(overrides.pop("trainer_config", {}))
        merged = {"trainer_config": trainer}
        merged.update(overrides.pop("overrides", {}))
        return write_config(overrides=merged, **overrides)

    return _make


def _invoke(args):
    return CliRunner().invoke(cli.main, args)


def _snapshot(root: Path) -> set:
    return {path.relative_to(root) for path in root.rglob("*")}


def _assert_nothing_happened(result, recorder, tmp_path, before):
    """The command failed cleanly: no traceback, no subprocess, no files touched."""
    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert recorder.calls == []
    assert not (tmp_path / "ckpt").exists()
    assert _snapshot(tmp_path) == before


# --- the happy path ----------------------------------------------------------------------


def test_run_stages_artifacts_and_invokes_the_backend(
    backend_stub, run_config, tmp_path
):
    path = run_config()
    result = _invoke(["run", str(path)])
    assert result.exit_code == 0, result.output

    run_dir = tmp_path / "ckpt" / "r1"
    resolved = run_dir / "resolved_config.yaml"
    assert resolved.is_file()
    assert (run_dir / "source_config.yaml").read_bytes() == path.read_bytes()

    ((argv, _kwargs),) = backend_stub.calls
    assert argv == [
        str(tmp_path / "bin" / "sleap-nn"),
        "train",
        "--config",
        str(resolved.resolve()),
    ]


def test_run_names_the_resolved_backend_before_starting(
    backend_stub, run_config, tmp_path
):
    """The only diagnostic for a wrong-environment pick, so it must precede the run."""
    result = _invoke(["run", str(run_config())])
    assert str(tmp_path / "bin" / "sleap-nn") in result.output


def test_run_reports_the_run_directory_on_success(backend_stub, run_config, tmp_path):
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 0, result.output
    assert str(tmp_path / "ckpt" / "r1") in result.output
    assert "resolved_config.yaml" in result.output
    assert "source_config.yaml" in result.output


def test_resolved_config_override_relocates_only_the_emitted_config(
    backend_stub, run_config, tmp_path
):
    elsewhere = tmp_path / "elsewhere" / "cfg.yaml"
    result = _invoke(["run", str(run_config()), "--resolved-config", str(elsewhere)])
    assert result.exit_code == 0, result.output
    assert elsewhere.is_file()
    assert not (tmp_path / "ckpt" / "r1" / "resolved_config.yaml").exists()
    assert (tmp_path / "ckpt" / "r1" / "source_config.yaml").is_file()


def test_run_echoes_the_skipped_deep_validation_note(backend_stub, run_config):
    """The gate is the console script; it does not imply `sleap_nn` is importable here.

    A PATH hit from another environment satisfies the gate while deep validation is
    skipped, and an operator about to spend hours on a run should be told that.
    """
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output.lower()


# --- step order: every cheap failure happens before any side effect ----------------------


def test_missing_backend_changes_nothing(monkeypatch, run_config, tmp_path):
    path = run_config()
    monkeypatch.setattr(
        backend,
        "resolve_sleap_nn",
        lambda: (_ for _ in ()).throw(backend.BackendError("nope")),
    )
    _Recorder.calls = []
    monkeypatch.setattr(backend.subprocess, "Popen", _Recorder)
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    _assert_nothing_happened(result, _Recorder, tmp_path, before)


def test_invalid_config_changes_nothing(backend_stub, run_config, tmp_path):
    path = run_config(drop=("trainer_config.seed",))
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    _assert_nothing_happened(result, backend_stub, tmp_path, before)
    assert "seed" in result.output


def test_malformed_yaml_changes_nothing(backend_stub, tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("experiment: [unbalanced\n", encoding="utf-8")
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    _assert_nothing_happened(result, backend_stub, tmp_path, before)


def test_nonexistent_config_changes_nothing(backend_stub, tmp_path):
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(tmp_path / "nope.yaml")])
    _assert_nothing_happened(result, backend_stub, tmp_path, before)


def test_inline_api_key_changes_nothing(backend_stub, run_config, tmp_path):
    path = run_config(overrides={"trainer_config": {"wandb": {"api_key": "deadbeef"}}})
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    _assert_nothing_happened(result, backend_stub, tmp_path, before)
    assert "api_key" in result.output


def test_wandb_enabled_without_a_credential_changes_nothing(
    backend_stub, run_config, tmp_path, monkeypatch, isolate_wandb_env
):
    path = run_config(
        overrides={
            "trainer_config": {
                "use_wandb": True,
                "wandb": {"entity": "e", "project": "p"},
            }
        }
    )
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    _assert_nothing_happened(result, backend_stub, tmp_path, before)


def test_unusable_run_name_changes_nothing(backend_stub, run_config, tmp_path):
    path = run_config(trainer_config={"run_name": "   "})
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    _assert_nothing_happened(result, backend_stub, tmp_path, before)
    assert "run_name" in result.output


def test_occupied_run_directory_changes_nothing(backend_stub, run_config, tmp_path):
    path = run_config()
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "best.ckpt").write_bytes(b"weights")
    before = _snapshot(tmp_path)
    result = _invoke(["run", str(path)])
    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert backend_stub.calls == []
    assert _snapshot(tmp_path) == before  # the previous run is untouched
    assert "run_name" in result.output


# --- exit status --------------------------------------------------------------------------


def test_backend_failure_propagates_without_a_success_line(backend_stub, run_config):
    backend_stub.statuses = [2]
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 2
    assert "OK:" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_signal_termination_becomes_128_plus_n(backend_stub, run_config):
    backend_stub.statuses = [-9]
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 137


def test_interrupt_reports_the_backends_status_not_a_traceback(
    backend_stub, run_config
):
    backend_stub.statuses = [KeyboardInterrupt(), -2]
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 130
    assert not isinstance(result.exception, KeyboardInterrupt)
    assert "Aborted!" not in result.output


def test_a_failed_run_keeps_its_artifacts(backend_stub, run_config, tmp_path):
    """They are the record of what was attempted; rolling them back destroys evidence."""
    backend_stub.statuses = [1]
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 1
    run_dir = tmp_path / "ckpt" / "r1"
    assert (run_dir / "resolved_config.yaml").is_file()
    assert (run_dir / "source_config.yaml").is_file()


# --- the base install must stay clean ------------------------------------------------------


def test_run_never_touches_sleap_nn_in_process(backend_stub, run_config, monkeypatch):
    """A tripwire, not a `sys.modules` check.

    ``assert "sleap_nn" not in sys.modules`` is vacuous wherever the extra is absent --
    which is every CI leg. This installs a module that raises on *any* attribute access,
    so a dynamic ``importlib.import_module("sleap_nn")`` would be caught too.
    """
    tripwire = types.ModuleType("sleap_nn")
    tripwire.__spec__ = importlib.machinery.ModuleSpec("sleap_nn", None)

    def _boom(name):
        raise AssertionError(f"run touched sleap_nn.{name} in-process")

    tripwire.__getattr__ = _boom
    monkeypatch.setitem(sys.modules, "sleap_nn", tripwire)
    result = _invoke(["run", str(run_config())])
    assert result.exit_code == 0, result.output


def test_no_module_spells_a_sleap_nn_import():
    """Belt-and-suspenders against the obvious spelling, at any nesting depth.

    Static only: it cannot see ``importlib.import_module``, which is what the tripwire
    above is for. ``config.py`` is excluded deliberately -- its lazy
    ``sleap_nn.config.training_job_config`` import is the *validation* API, not the
    training entry point.
    """
    root = Path(cli.__file__).parent
    for module in (root / "cli.py", root / "backend.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(
                name == "sleap_nn" or name.startswith("sleap_nn.") for name in names
            ), f"{module.name} imports sleap_nn directly"


def test_the_gate_did_not_leak_into_validate_or_emit(monkeypatch, run_config, tmp_path):
    """`validate` and `emit` stay base-install safe beside a train-gated command."""
    monkeypatch.setattr(
        backend,
        "resolve_sleap_nn",
        lambda: (_ for _ in ()).throw(backend.BackendError("no backend here")),
    )
    path = run_config()
    assert _invoke(["validate", str(path)]).exit_code == 0
    out = tmp_path / "emitted.yaml"
    assert _invoke(["emit", str(path), "-o", str(out)]).exit_code == 0
    assert out.is_file()
