"""Tests for locating and driving the ``sleap-nn`` training backend.

Base-install safe: CI never installs the ``train`` extra, so nothing here executes the
real backend. Resolution is exercised against **stub** console scripts written into
``tmp_path``, and the interpreter-side lookup is driven through the
``backend._interpreter_scripts_dir`` seam.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sleap_roots_training import backend
from sleap_roots_training import config as training_config


def _make_stub(directory: Path) -> Path:
    """Write an executable ``sleap-nn`` stub into ``directory`` and return its path.

    The name is platform-dependent on purpose: Windows ``shutil.which`` on Python 3.11
    only tries ``cmd + ext`` for each ``PATHEXT`` entry, never the bare extensionless
    name, so an unsuffixed stub is invisible on that leg (3.12 appends the bare name,
    which is why this would otherwise pass on one Windows cell and fail on the other).
    """
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / ("sleap-nn.exe" if os.name == "nt" else "sleap-nn")
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    if os.name != "nt":
        stub.chmod(0o755)  # `which` checks os.X_OK; a no-op on Windows
    return stub


@pytest.fixture(autouse=True)
def _stable_cwd(tmp_path, monkeypatch):
    """Keep the current directory out of the search.

    Python 3.11's ``shutil.which`` prepends ``os.curdir`` on win32 **even when ``path=``
    is passed**, mimicking ``cmd.exe``. Without this, a stub in the invoking directory
    would decide the result on that leg.
    """
    monkeypatch.chdir(tmp_path)


def test_interpreter_scripts_dir_wins_over_path(tmp_path, monkeypatch):
    scripts = _make_stub(tmp_path / "scripts")
    _make_stub(tmp_path / "elsewhere")
    monkeypatch.setattr(
        backend, "_interpreter_scripts_dir", lambda: str(scripts.parent)
    )
    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))
    assert backend.resolve_sleap_nn().resolve() == scripts.resolve()


def test_interpreter_directory_wins_over_path(tmp_path, monkeypatch):
    """The middle tier: no console script in the scripts dir, one beside the interpreter.

    This is the layout the scripts-dir lookup does not cover — a relocated or vendored
    scheme where the interpreter does not sit in its own ``sysconfig`` scripts path.
    """
    beside = _make_stub(tmp_path / "interp")
    _make_stub(tmp_path / "elsewhere")
    monkeypatch.setattr(
        backend, "_interpreter_scripts_dir", lambda: str(tmp_path / "empty")
    )
    monkeypatch.setattr(backend.sys, "executable", str(beside.parent / "python"))
    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))
    assert backend.resolve_sleap_nn().resolve() == beside.resolve()


def test_path_is_the_fallback(tmp_path, monkeypatch):
    on_path = _make_stub(tmp_path / "elsewhere")
    monkeypatch.setattr(
        backend, "_interpreter_scripts_dir", lambda: str(tmp_path / "empty")
    )
    monkeypatch.setattr(backend.sys, "executable", str(tmp_path / "empty" / "python"))
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert backend.resolve_sleap_nn().resolve() == on_path.resolve()


def test_missing_backend_raises_backend_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backend, "_interpreter_scripts_dir", lambda: str(tmp_path / "empty")
    )
    monkeypatch.setattr(backend.sys, "executable", str(tmp_path / "empty" / "python"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(backend.BackendError):
        backend.resolve_sleap_nn()


def test_missing_backend_message_names_the_install(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backend, "_interpreter_scripts_dir", lambda: str(tmp_path / "empty")
    )
    monkeypatch.setattr(backend.sys, "executable", str(tmp_path / "empty" / "python"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(backend.BackendError) as excinfo:
        backend.resolve_sleap_nn()
    message = str(excinfo.value)
    assert "sleap-roots-training[train]" in message
    assert (
        "uvx --from" in message
    )  # the isolated-install case, where pip install is wrong
    assert "docs/training-backend.md" in message


def test_interpreter_scripts_dir_is_this_environments_script_dir():
    """The seam must name the directory this environment's console scripts live in.

    `black` is a dev-group dependency, so it is present on every CI leg. This is the
    test that catches a regression to ``Path(sys.executable).parent``, which is the
    environment root -- not ``Scripts\\`` -- for conda and base Windows installs.
    """
    black = shutil.which("black")
    if black is None:
        pytest.skip("black is not installed in this environment")
    assert (
        Path(backend._interpreter_scripts_dir()).resolve()
        == Path(black).parent.resolve()
    )


# --- destination policy + provenance artifacts -------------------------------------------


def _cfg(write_config, **kwargs):
    """Load a config written by the shared factory, returning (cfg, path)."""
    path = write_config(**kwargs)
    return training_config.load_config(path), path


def test_run_directory_is_ckpt_dir_joined_with_run_name(write_config, tmp_path):
    cfg, _ = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    assert backend.run_directory(cfg) == tmp_path / "ckpt" / "r1"


def test_unset_ckpt_dir_follows_the_backends_own_default(write_config, tmp_path):
    """sleap-nn 0.2.0 defaults `ckpt_dir` to "." (config/trainer_config.py:368)."""
    cfg, _ = _cfg(write_config, drop=("trainer_config.ckpt_dir",))
    assert backend.run_directory(cfg) == Path(".") / "arabidopsis_primary_cylinder"


def test_relative_ckpt_dir_resolves_against_the_process_cwd(write_config, tmp_path):
    """The backend resolves it against *its* cwd, which it inherits from ours."""
    cfg, _ = _cfg(
        write_config,
        overrides={"trainer_config": {"ckpt_dir": "models", "run_name": "r1"}},
    )
    assert (tmp_path / backend.run_directory(cfg)).parent == tmp_path / "models"


@pytest.mark.parametrize("run_name", [None, "", "   ", "None"])
def test_unusable_run_name_is_refused(write_config, run_name):
    """Empty/`"None"` are what the backend itself treats as unset (model_trainer.py:491).

    It would then generate `<timestamp>.<model_type>.n=<N>` -- a directory we cannot
    predict -- so refusing beats guessing.
    """
    if run_name is None:
        cfg, _ = _cfg(write_config, drop=("trainer_config.run_name",))
    else:
        cfg, _ = _cfg(
            write_config, overrides={"trainer_config": {"run_name": run_name}}
        )
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


@pytest.mark.parametrize(
    "run_name",
    [
        "a/b",
        "a\\b",  # one component to PurePosixPath, two to PureWindowsPath
        "../escape",
        "/tmp/absolute",
        "C:foo",  # drive-RELATIVE: is_absolute() is False and there is no separator...
        "C:\\abs",
        "..",  # one component under both flavours, yet climbs out of ckpt_dir
        ".",
        "...",
        "r1 ",  # Windows strips the trailing space: names `r1` there, `r1 ` here
        "r1.",
        "NUL ",  # the trailing space also walked past the device-name check
    ],
)
def test_run_name_that_escapes_the_run_directory_is_refused(write_config, run_name):
    """`Path("ckpt") / "/tmp/x"` evaluates to `/tmp/x`, escaping ckpt_dir entirely.

    The `C:foo` case is why this is a component count rather than
    ``is_absolute()`` + a separator scan: that pair reports the name as safe, while
    ``PureWindowsPath("ckpt") / "C:foo"`` still evaluates to ``C:foo`` -- pathlib drops the
    left-hand side as soon as the right-hand side carries a drive.
    """
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"run_name": run_name}})
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


@pytest.mark.parametrize(
    "run_name", ["has:colon", "star*", 'quo"te', "pipe|d", "lt<gt>"]
)
def test_run_name_with_windows_reserved_characters_is_refused(write_config, run_name):
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"run_name": run_name}})
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


@pytest.mark.parametrize("run_name", ["a\tb", "a\nb", "a\x00b"])
def test_run_name_with_control_characters_is_refused(write_config, run_name):
    """Rejected up front rather than surfacing later as a raw OSError from mkdir."""
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"run_name": run_name}})
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


@pytest.mark.parametrize("run_name", ["con", "AUX", "nul.txt", "com1", "LPT9.yaml"])
def test_run_name_that_is_a_windows_device_name_is_refused(write_config, run_name):
    """Refused on every platform, not just Windows.

    These are legal directory names on POSIX, so a name accepted on the authoring Mac would
    fail only on the training box -- the worst place to discover it.
    """
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"run_name": run_name}})
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


@pytest.mark.parametrize("run_name", [5, True, 1.5])
def test_non_string_run_name_is_refused(write_config, run_name):
    """A malformed YAML can yield an int/bool where a name belongs."""
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"run_name": run_name}})
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


@pytest.mark.parametrize(
    "run_name",
    ["r1", "runcmd_verify_20260819", "baseline_os4_seed42", "r1.v2", "r-1_2", " lead"],
)
def test_the_run_directory_is_always_inside_ckpt_dir(write_config, tmp_path, run_name):
    """The invariant the path-escape bugs broke, asserted so that it can actually fail.

    Deliberately a **containment check on resolved paths**, not an assertion about `.parent`.
    The earlier `.parent` form was written from the implementation rather than from the
    property, and `Path("ckpt/..").parent` *is* `Path("ckpt")` -- so it passed on the exact
    input (`run_name: ".."`) that violates the invariant its own docstring stated. Containment
    cannot be satisfied by a name that climbs out, so it catches the whole family rather than
    one enumerated shape at a time.
    """
    cfg, _ = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": run_name}
        },
    )
    (tmp_path / "ckpt").mkdir(exist_ok=True)
    run_dir = backend.run_directory(cfg)
    assert (tmp_path / "ckpt").resolve() in run_dir.resolve().parents


def test_a_run_path_that_exists_as_a_file_is_refused(tmp_path):
    """Named explicitly rather than surfacing later as an mkdir failure."""
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.parent.mkdir(parents=True)
    run_dir.write_text("not a directory", encoding="utf-8")
    with pytest.raises(backend.BackendError, match="not a directory"):
        backend.check_run_directory(run_dir)


def test_run_directory_holding_a_checkpoint_is_refused(tmp_path):
    """The backend suffixes to `<run_name>-1` when best.ckpt exists (model_trainer.py:522).

    Anything staged under `<run_name>/` would then describe a different run than the one
    beside it, so this refuses rather than stranding the artifacts.
    """
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "best.ckpt").write_bytes(b"weights")
    with pytest.raises(backend.BackendError, match="run_name"):
        backend.check_run_directory(run_dir)


def test_run_directory_holding_a_backend_config_is_refused(tmp_path):
    """Stricter than the backend's own trigger, deliberately.

    A `save_ckpt: false` run never writes best.ckpt, so the backend silently reuses the
    directory; `training_config.yaml` is the marker that a run completed there anyway.
    """
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "training_config.yaml").write_text("{}", encoding="utf-8")
    with pytest.raises(backend.BackendError, match="run_name"):
        backend.check_run_directory(run_dir)


def test_run_directory_without_run_evidence_is_the_retry_case(tmp_path):
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "emitted_config.yaml").write_text("stale", encoding="utf-8")
    backend.check_run_directory(run_dir)  # must not raise


def test_resolved_config_path_defaults_into_the_run_directory(tmp_path):
    run_dir = tmp_path / "ckpt" / "r1"
    assert (
        backend.resolved_config_path(run_dir, None) == run_dir / "emitted_config.yaml"
    )


def test_resolved_config_path_honors_the_override(tmp_path):
    run_dir = tmp_path / "ckpt" / "r1"
    override = tmp_path / "elsewhere" / "cfg.yaml"
    assert backend.resolved_config_path(run_dir, override) == override


def test_stage_writes_both_artifacts(write_config, tmp_path):
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    dest = backend.resolved_config_path(run_dir, None)
    backend.stage_artifacts(cfg, source, run_dir, dest)

    resolved_bytes = dest.read_bytes()
    assert resolved_bytes == training_config.to_sleap_nn_yaml(cfg).encode("utf-8")
    assert b"\r" not in resolved_bytes
    assert "experiment" not in dest.read_text(encoding="utf-8")
    for block in ("data_config", "model_config", "trainer_config"):
        assert block in dest.read_text(encoding="utf-8")

    source_copy = run_dir / "source_config.yaml"
    assert source_copy.read_bytes() == source.read_bytes()
    assert "experiment" in source_copy.read_text(encoding="utf-8")


def test_stage_creates_missing_parent_directories(write_config, tmp_path):
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {
                "ckpt_dir": str(tmp_path / "deep" / "nested"),
                "run_name": "r1",
            }
        },
    )
    run_dir = backend.run_directory(cfg)
    dest = backend.resolved_config_path(run_dir, None)
    backend.stage_artifacts(cfg, source, run_dir, dest)
    assert dest.is_file()


def test_stage_refuses_a_destination_whose_parent_is_a_file(write_config, tmp_path):
    """Portable: `chmod(0o555)` denies nothing on Windows, nor for root on POSIX."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file", encoding="utf-8")
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, blocker / "resolved.yaml")


def test_stage_refuses_a_directory_as_the_resolved_destination(write_config, tmp_path):
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    a_dir = tmp_path / "a_dir"
    a_dir.mkdir()
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, a_dir)


def test_stage_refuses_to_overwrite_the_source_config(write_config, tmp_path):
    """Overwriting the source with its experiment-stripped form destroys the run identity."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, source)
    assert "experiment" in source.read_text(encoding="utf-8")


def test_stage_refuses_an_override_colliding_with_the_source_copy(
    write_config, tmp_path
):
    """A relative override can resolve onto an artifact name `run` writes itself."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / "source_config.yaml")


def test_stage_leaves_no_truncated_artifact_when_the_write_fails(
    write_config, tmp_path, monkeypatch
):
    """A failed write must not leave a partial file the next run reads as real."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    dest = backend.resolved_config_path(run_dir, None)

    def _boom(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(backend.os, "replace", _boom)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, dest)
    assert not dest.exists()
    assert list(run_dir.glob("*.tmp*")) == []  # the temp file is cleaned up too


def test_stage_rechecks_the_run_directory_before_writing(write_config, tmp_path):
    """TOCTOU: a checkpoint appearing after the caller's check must still be refused."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    backend.check_run_directory(run_dir)  # passes: nothing there yet
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "best.ckpt").write_bytes(b"weights")  # ...appears in the window
    with pytest.raises(backend.BackendError, match="run_name"):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / "emitted_config.yaml")


def test_a_run_name_too_long_for_the_filesystem_fails_cleanly(write_config, tmp_path):
    """Long / non-ASCII names hit ENAMETOOLONG (POSIX) or MAX_PATH (Windows).

    Either way it must surface as BackendError, never as a raw OSError traceback.
    """
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {
                "ckpt_dir": str(tmp_path / "ckpt"),
                "run_name": "ünïcøde" * 60,
            }
        },
    )
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / "emitted_config.yaml")


def test_inline_wandb_api_key_is_refused(write_config):
    """registry/publish.py uploads the whole run dir, so a persisted key would ship."""
    cfg, _ = _cfg(
        write_config,
        overrides={"trainer_config": {"wandb": {"api_key": "deadbeef"}}},
    )
    with pytest.raises(backend.BackendError, match="api_key"):
        backend.reject_inline_api_key(cfg)


@pytest.mark.parametrize("value", [None, ""])
def test_absent_or_empty_api_key_is_fine(write_config, value):
    overrides = (
        {"trainer_config": {"wandb": {"api_key": value}}} if value is not None else None
    )
    cfg, _ = _cfg(write_config, overrides=overrides)
    backend.reject_inline_api_key(cfg)  # must not raise


# --- invocation + exit-status translation ------------------------------------------------


class _FakePopen:
    """A stand-in for ``subprocess.Popen`` recording how it was called.

    ``wait`` yields ``statuses`` in order; a ``KeyboardInterrupt`` entry is *raised*
    instead of returned, which is what really happens on Ctrl-C (SIGINT reaches this
    process too, not only the child).
    """

    instances: list = []

    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.killed = False
        self.terminated = False
        self.waits = 0
        self._statuses = list(type(self).statuses)
        type(self).instances.append(self)

    def wait(self):
        self.waits += 1
        status = self._statuses.pop(0)
        if isinstance(status, BaseException):
            raise status
        return status

    def kill(self):
        self.killed = True

    def terminate(self):
        self.terminated = True


@pytest.fixture
def fake_popen(monkeypatch):
    """Install ``_FakePopen`` and return it, with per-test ``statuses`` to yield."""
    _FakePopen.instances = []
    _FakePopen.statuses = [0]
    monkeypatch.setattr(backend.subprocess, "Popen", _FakePopen)
    return _FakePopen


def test_build_argv_is_exactly_the_documented_vector(tmp_path):
    binary = tmp_path / "bin" / "sleap-nn"
    dest = tmp_path / "ckpt" / "r1" / "emitted_config.yaml"
    assert backend.build_argv(binary, dest) == [
        str(binary),
        "train",
        "--config",
        str(dest.resolve()),
    ]


def test_build_argv_absolutizes_the_config_path(tmp_path, monkeypatch):
    """The child inherits our cwd, but the backend hands the path to Hydra, which
    resolves it itself -- passing it absolute keeps the two from disagreeing."""
    monkeypatch.chdir(tmp_path)
    argv = backend.build_argv(Path("sleap-nn"), Path("relative.yaml"))
    assert Path(argv[3]).is_absolute()


def test_invocation_is_a_bare_vector_with_no_redirection(fake_popen, tmp_path):
    backend.run_backend([str(tmp_path / "sleap-nn"), "train", "--config", "x.yaml"])
    (call,) = fake_popen.instances  # exactly one subprocess
    assert "shell" not in call.kwargs  # a vector, never a command string
    assert "env" not in call.kwargs  # the operator's environment reaches the backend
    assert "cwd" not in call.kwargs  # relative dataset/ckpt paths must agree with ours
    for redirect in ("stdout", "stderr", "capture_output"):
        assert (
            redirect not in call.kwargs
        )  # streams are inherited, so a run streams live
    assert set(call.kwargs) == set()  # nothing smuggled in later, either


def test_success_status_is_zero(fake_popen, tmp_path):
    fake_popen.statuses = [0]
    outcome = backend.run_backend(["sleap-nn"])
    assert outcome.exit_code == 0
    assert outcome.note is None


def test_positive_status_propagates_verbatim(fake_popen):
    fake_popen.statuses = [2]
    assert backend.run_backend(["sleap-nn"]).exit_code == 2


def test_signal_termination_maps_to_128_plus_n(fake_popen):
    """POSIX reports a signal-killed child as a negative return code."""
    fake_popen.statuses = [-9]
    outcome = backend.run_backend(["sleap-nn"])
    assert outcome.exit_code == 137
    assert "signal 9" in outcome.note


def test_windows_style_status_is_not_translated(fake_popen):
    """A large NTSTATUS is a status, not a signal, and does not fit an exit code.

    0xC0000005 (access violation) rather than 0xC000013A: the latter is Ctrl-C, which now has
    its own translation to 130, so it is no longer an example of the pass-through path.
    """
    fake_popen.statuses = [3221225477]
    outcome = backend.run_backend(["sleap-nn"])
    assert outcome.exit_code != 0
    assert outcome.exit_code <= 255
    assert "3221225477" in outcome.note


def test_status_above_the_exit_code_range_stays_a_failure(fake_popen):
    """POSIX truncates a real exit status to 8 bits, so 256 must not become 0."""
    fake_popen.statuses = [256]
    outcome = backend.run_backend(["sleap-nn"])
    assert outcome.exit_code != 0
    assert outcome.exit_code <= 255


def test_interrupt_lets_the_backend_own_the_signal(fake_popen):
    """Ctrl-C reaches both processes; the backend must be allowed to shut down.

    ``subprocess.run`` is unusable here precisely because it responds to the parent's
    KeyboardInterrupt by SIGKILLing the child and re-raising -- which both destroys
    Lightning's checkpoint-on-interrupt and makes the signal branch unreachable.
    """
    fake_popen.statuses = [KeyboardInterrupt(), -2]
    outcome = backend.run_backend(["sleap-nn"])
    (call,) = fake_popen.instances
    assert not call.killed and not call.terminated
    assert call.waits == 2  # waited again rather than giving up
    assert outcome.exit_code == 130  # 128 + SIGINT


# --- the real Popen path (no seams) --------------------------------------------------------

#: A child that writes to both streams and exits with a chosen status. Driven through
#: `sys.executable` rather than a shell stub so this runs on **Windows** too -- the OS the
#: target GPU box runs, and the one where a `#!` script is not executable and a `.bat`
#: cannot be launched by CreateProcess without a shell.
_CHILD = (
    "import sys; sys.stdout.write('child-stdout\\n'); "
    "sys.stderr.write('child-stderr\\n'); sys.exit(int(sys.argv[1]))"
)


def test_real_subprocess_inherits_both_streams(capfd):
    """The behavioral proof of stream inheritance the call-shape test cannot give.

    ``capfd`` captures at the file-descriptor level; ``capsys`` cannot see a child process.
    """
    outcome = backend.run_backend([sys.executable, "-c", _CHILD, "0"])
    captured = capfd.readouterr()
    assert "child-stdout" in captured.out
    assert "child-stderr" in captured.err
    assert outcome.exit_code == 0


@pytest.mark.parametrize("status", [0, 2, 7])
def test_real_subprocess_propagates_its_exit_status(status, capfd):
    assert (
        backend.run_backend([sys.executable, "-c", _CHILD, str(status)]).exit_code
        == status
    )
    capfd.readouterr()  # drain the child's output so it does not leak into the report


@pytest.mark.integration
def test_installed_backend_still_accepts_config_flag():
    """The upstream-compatibility check the argv contract test cannot perform.

    ``build_argv`` asserts what *we* emit; it cannot notice sleap-nn renaming the flag.
    This is the test that fails first at the Tier 6 bump to the 0.3.0 mask line, before a
    long run is wasted on it. Inert in CI, which never installs the extra.
    """
    pytest.importorskip("sleap_nn")
    binary = backend.resolve_sleap_nn()
    completed = subprocess.run(
        [str(binary), "train", "--help"], capture_output=True, text=True, timeout=120
    )
    assert "--config" in (completed.stdout + completed.stderr)


# --- interpolation, override gating, resolution hijack, ckpt_dir ---------------------------


def test_unresolvable_interpolation_is_a_clean_error_not_a_traceback(write_config):
    """`${oc.env:UNSET}` in a gated field must not escape as an OmegaConf exception.

    The credential section pushes operators toward `${oc.env:WANDB_API_KEY}`, so an unexported
    variable is an ordinary mistake, not an exotic one.
    """
    cfg, _ = _cfg(
        write_config,
        overrides={
            "trainer_config": {"run_name": "${oc.env:SLEAP_ROOTS_NOT_SET_ANYWHERE}"}
        },
    )
    with pytest.raises(backend.BackendError):
        backend.run_directory(cfg)


def test_interpolation_into_the_experiment_block_is_refused(write_config, tmp_path):
    """The load-bearing half: it resolves *here* and cannot resolve for the backend.

    `run_name: ${experiment.species}_v1` resolves against the full config, so every gate would
    validate `arabidopsis_v1` and stage the artifacts there -- but the emitted config has the
    `experiment` block stripped and is written unresolved, so the backend cannot reload it. The
    run would be gated, staged and reported against a value the backend never sees.
    """
    cfg, _ = _cfg(
        write_config,
        overrides={"trainer_config": {"run_name": "${experiment.species}_v1"}},
    )
    with pytest.raises(backend.BackendError, match="experiment"):
        backend.check_emitted_config_resolvable(cfg)


def test_a_resolvable_config_passes_the_emitted_resolvability_check(write_config):
    cfg, _ = _cfg(write_config)
    backend.check_emitted_config_resolvable(cfg)  # must not raise


def test_override_naming_a_run_evidence_file_is_refused(write_config, tmp_path):
    """4b: `run` must not be able to fabricate the completion evidence it later refuses.

    Writing the emitted config as `training_config.yaml` makes the next plain retry fail the
    reuse check forever -- and the design deliberately ships no `--force`, so recovery would be
    hand-deleting files.
    """
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    for marker in backend.RUN_EVIDENCE:
        with pytest.raises(backend.BackendError, match="run"):
            backend.stage_artifacts(cfg, source, run_dir, run_dir / marker)


def test_override_pointing_into_a_finished_run_is_refused(write_config, tmp_path):
    """4a: the override bypassed `check_run_directory` entirely."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    other = tmp_path / "ckpt" / "otherrun"
    other.mkdir(parents=True)
    (other / "best.ckpt").write_bytes(b"weights")
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError, match="previous run"):
        backend.stage_artifacts(cfg, source, run_dir, other / "emitted.yaml")


def test_resolution_ignores_a_relative_hit_from_the_current_directory(
    tmp_path, monkeypatch
):
    """Python 3.11 on win32 prepends `os.curdir` even when `path=` is passed.

    `build.yml` pins 3.11, and the GPU box is Windows, so a stray `sleap-nn.exe` in the
    invocation directory would beat the interpreter's `Scripts\\` -- defeating the ordering this
    module is built around, and printing a bare relative name so the "visibility" mitigation
    fails exactly when the hazard fires. Simulated here by a `which` that returns a relative hit.
    """
    scripts = tmp_path / "scripts"
    _make_stub(scripts)
    decoy = "./sleap-nn.exe"

    def fake_which(name, path=None):
        return decoy if path is not None else None

    monkeypatch.setattr(backend.shutil, "which", fake_which)
    monkeypatch.setattr(backend, "_interpreter_scripts_dir", lambda: str(scripts))
    with pytest.raises(backend.BackendError):
        backend.resolve_sleap_nn()


def test_resolved_backend_path_is_absolute(tmp_path, monkeypatch):
    stub = _make_stub(tmp_path / "scripts")
    monkeypatch.setattr(backend, "_interpreter_scripts_dir", lambda: str(stub.parent))
    assert backend.resolve_sleap_nn().is_absolute()


@pytest.mark.parametrize("ckpt_dir", [5, True, ["a", "b"], {"a": 1}, "", "   "])
def test_unusable_ckpt_dir_is_refused(write_config, ckpt_dir):
    """`ckpt_dir` supplies the left-hand side of every path this design guards.

    `config.py` type-checks `seed`, `use_wandb` and the preprocessing flags; this field was the
    odd one out, and a falsy value silently fell through to `.` -- so provenance went to a
    directory the backend would never train into.
    """
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"ckpt_dir": ckpt_dir}})
    with pytest.raises(backend.BackendError, match="trainer_config.ckpt_dir"):
        backend.run_directory(cfg)


def test_absent_ckpt_dir_still_follows_the_backend_default(write_config):
    """Absent is not the same as malformed: the documented `.` default still applies."""
    cfg, _ = _cfg(write_config, drop=("trainer_config.ckpt_dir",))
    assert backend.run_directory(cfg) == Path(".") / "arabidopsis_primary_cylinder"


@pytest.mark.parametrize("marker", backend.RUN_EVIDENCE)
def test_every_run_evidence_marker_triggers_the_refusal(tmp_path, marker):
    """Parametrized over the constant so a new marker cannot be added without coverage."""
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / marker).write_bytes(b"x")
    with pytest.raises(backend.BackendError, match="previous run"):
        backend.check_run_directory(run_dir)


def test_a_backend_that_cannot_be_launched_is_a_clean_error(tmp_path, monkeypatch):
    """`Popen` itself raises for a truncated wheel or a `.PY` PATHEXT hit.

    It is called after the artifacts are staged, so an uncaught OSError here would surface as a
    traceback on top of a half-completed run.
    """

    def boom(argv, **kwargs):
        raise OSError(8, "Exec format error")

    monkeypatch.setattr(backend.subprocess, "Popen", boom)
    with pytest.raises(backend.BackendError, match="sleap-nn"):
        backend.run_backend([str(tmp_path / "sleap-nn"), "train"])


def test_windows_ctrl_c_status_is_reported_as_an_interrupt(fake_popen):
    """0xC000013A is STATUS_CONTROL_C_EXIT -- an interrupt, not an opaque 10-digit status."""
    fake_popen.statuses = [3221225786]
    outcome = backend.run_backend(["sleap-nn"])
    assert outcome.exit_code == 130
    assert "interrupt" in outcome.note.lower()


def test_a_second_interrupt_escalates_instead_of_looping_forever(fake_popen):
    """design.md promised an escape hatch that did not exist: every Ctrl-C hit the same
    `continue`, so a child ignoring SIGINT could not be aborted at all."""
    fake_popen.statuses = [KeyboardInterrupt(), KeyboardInterrupt(), -15]
    outcome = backend.run_backend(["sleap-nn"])
    (call,) = fake_popen.instances
    assert call.terminated  # the second interrupt escalated...
    assert not call.killed  # ...without jumping straight to SIGKILL
    assert outcome.exit_code == 143


def test_the_first_interrupt_still_lets_the_backend_shut_down(fake_popen):
    fake_popen.statuses = [KeyboardInterrupt(), -2]
    outcome = backend.run_backend(["sleap-nn"])
    (call,) = fake_popen.instances
    assert not call.terminated and not call.killed
    assert outcome.exit_code == 130


def test_the_source_config_is_written_before_the_emitted_one(
    write_config, tmp_path, monkeypatch
):
    """Ordering matters when the second write fails.

    `source_config.yaml` is the only artifact carrying the `experiment` block, so a failure that
    left the run directory holding just the emitted config would lose the one thing nothing else
    records.
    """
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    calls = []
    real_write = backend._atomic_write

    def failing_write(path, payload):
        calls.append(path)
        if len(calls) == 2:
            raise OSError(28, "No space left on device")
        real_write(path, payload)

    monkeypatch.setattr(backend, "_atomic_write", failing_write)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / "emitted_config.yaml")
    assert calls[0].name == backend.SOURCE_CONFIG_NAME
    assert (run_dir / backend.SOURCE_CONFIG_NAME).is_file()


def test_backend_version_reports_what_the_binary_prints(tmp_path):
    """A real probe, not a stub: this is the only record of the backend for an early death."""
    if os.name == "nt":
        pytest.skip("POSIX: fabricating an executable stub")
    stub = tmp_path / "sleap-nn"
    stub.write_text("#!/bin/sh\necho 'sleap-nn 9.9.9'\n", encoding="utf-8")
    stub.chmod(0o755)
    assert backend.backend_version(stub) == "sleap-nn 9.9.9"


def test_backend_version_is_a_diagnostic_and_never_a_gate(tmp_path):
    """A backend that cannot report a version still runs -- this must not raise."""
    assert backend.backend_version(tmp_path / "does_not_exist") is None


def test_a_third_interrupt_kills(fake_popen):
    """The ladder has a floor: forwarded, then terminate, then kill."""
    fake_popen.statuses = [
        KeyboardInterrupt(),
        KeyboardInterrupt(),
        KeyboardInterrupt(),
        -9,
    ]
    outcome = backend.run_backend(["sleap-nn"])
    (call,) = fake_popen.instances
    assert call.terminated and call.killed
    assert outcome.exit_code == 137
