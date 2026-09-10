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
import threading
import time
from pathlib import Path

import pytest

from omegaconf import OmegaConf

from sleap_roots_training import backend
from sleap_roots_training import config as training_config


def _mangled(name: str) -> str:
    """What Win32 would actually create for ``name``, folded for case.

    Deliberately the test module's **own** copy of the rule rather than an import of
    ``backend._mangled``: a test that reuses the implementation's helper cannot notice the
    implementation getting the rule wrong.
    """
    return name.rstrip(". ").casefold()


#: Destination spellings built from three independent mangling rules rather than listed by
#: hand. Every name a run directory must never gain, crossed with the suffixes Win32 strips at
#: creation time and the case transforms NTFS and APFS fold. The point is not the count -- it
#: is that a spelling nobody enumerated is generated, and that the assertion below is the
#: property rather than membership of this product.
_MANGLING_SUFFIXES = ("", ".", " ", "..", ". ", " .", "...")
_CASE_FORMS = (str.lower, str.upper, str.capitalize)


def _destination_spellings(bases):
    """Yield every case x trailing-mangling spelling of each name in ``bases``."""
    for base in bases:
        for case in _CASE_FORMS:
            for suffix in _MANGLING_SUFFIXES:
                yield case(base) + suffix


#: Fragments that have each, at some point in this change's history, turned a plain name into
#: an escape: relative references, both separators, a Windows drive prefix, a home reference,
#: the characters Win32 strips, and an invisible Unicode format character.
_NAME_FRAGMENTS = ("", ".", "..", "...", "/", "\\", "C:", "~", " ", "\t", "\u200b")

#: Seeds chosen so the product covers an ordinary name, a device name, and an evidence name.
_NAME_SEEDS = ("r1", "run", "NUL", "best.ckpt")


def _generated_run_names():
    """Yield run names as a product of fragments, not as a hand-written list."""
    for seed in _NAME_SEEDS:
        for prefix in _NAME_FRAGMENTS:
            for suffix in _NAME_FRAGMENTS:
                yield f"{prefix}{seed}{suffix}"
    yield from _NAME_FRAGMENTS


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
    # Containment is the property that catches every escaping shape; the direct-child assertion
    # beside it pins the single-component rule, which containment alone does not (a/b is
    # contained too). Both, so neither half rests on the refusal list next door.
    assert (tmp_path / "ckpt").resolve() in run_dir.resolve().parents
    assert run_dir.resolve().parent == (tmp_path / "ckpt").resolve()


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
    assert backend.emitted_config_path(run_dir, None) == run_dir / "emitted_config.yaml"


def test_resolved_config_path_honors_the_override(tmp_path):
    run_dir = tmp_path / "ckpt" / "r1"
    override = tmp_path / "elsewhere" / "cfg.yaml"
    assert backend.emitted_config_path(run_dir, override) == override


def test_stage_writes_both_artifacts(write_config, tmp_path):
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    dest = backend.emitted_config_path(run_dir, None)
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
    dest = backend.emitted_config_path(run_dir, None)
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
    dest = backend.emitted_config_path(run_dir, None)

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


def test_an_api_key_interpolation_is_not_an_inline_credential(
    write_config, monkeypatch
):
    """The guard reads the **unresolved** node, so the documented pattern is not refused.

    Reading through ``OmegaConf.select`` *resolves*, so with ``WANDB_API_KEY`` exported the
    guard saw the secret and refused a config whose artifact would have carried only the
    literal ``${oc.env:WANDB_API_KEY}`` -- the check's own rationale ("the key would ship with
    it") does not apply to that input, and the remedy it printed was what the operator had
    already done. The variable is set deliberately: with it unset the old code raised a
    different error instead, so the bug was invisible to any test that left it unset.
    """
    monkeypatch.setenv("WANDB_API_KEY", "supersecret")
    cfg, _ = _cfg(
        write_config,
        overrides={"trainer_config": {"wandb": {"api_key": "${oc.env:WANDB_API_KEY}"}}},
    )
    backend.reject_inline_api_key(cfg)  # must not raise


def test_an_api_key_written_literally_is_still_refused(write_config, monkeypatch):
    """The relaxation above is about *interpolations*, not about literals.

    A literal is what gets persisted verbatim into a directory a model publish uploads, which
    is what the guard exists for. Exercised with ``WANDB_API_KEY`` exported too, so the
    refusal cannot be passing merely because nothing in the environment resolves.
    """
    monkeypatch.setenv("WANDB_API_KEY", "irrelevant")
    cfg, _ = _cfg(
        write_config,
        overrides={"trainer_config": {"wandb": {"api_key": "literal-secret"}}},
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
        self.returncode = None
        self._statuses = list(type(self).statuses)
        type(self).instances.append(self)

    def wait(self, timeout=None):
        """Model the **bounded** wait the module now uses.

        `timeout` is accepted rather than ignored on purpose: a fake that only implements the
        blocking signature would keep passing if the production code went back to a blocking
        wait, which is precisely the defect this signature exists to prevent. A queued
        `TimeoutExpired` is raised like any other status, so the poll branch is exercised.
        """
        self.waits += 1
        status = self._statuses.pop(0)
        if isinstance(status, BaseException):
            raise status
        self.returncode = status
        return status

    def poll(self):
        return self.returncode

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


#: A child that ignores SIGINT and then sleeps -- the shape of a trainer with a graceful
#: shutdown handler, which is exactly the case the escalation ladder exists for.
_DEAF_CHILD = (
    "import signal, sys, time; signal.signal(signal.SIGINT, signal.SIG_IGN); "
    "sys.stderr.write('ready\\n'); sys.stderr.flush(); time.sleep(30)"
)


def test_repeated_interrupts_reach_the_escalation_while_the_child_runs(capfd):
    """The escalation ladder is reachable *during* the run, not only after it ends.

    `Popen.wait()` with no timeout is a non-alertable `WaitForSingleObject(INFINITE)` on
    Windows, so a pending interrupt is deferred until the child exits -- on the one platform
    that trains. The common case still looked fine, because the console delivers `CTRL_C_EVENT`
    to the child directly; but "press Ctrl-C again to terminate it" printed after the child had
    already gone, and for a child that *defers* the interrupt the second and third Ctrl-C could
    not be delivered at all, so `terminate()` and `kill()` never ran.

    The existing interrupt tests raise `KeyboardInterrupt` synchronously from a fake `wait()`,
    so they cannot see this: the fake has no blocking syscall to be stuck in. This drives a
    **real** subprocess and simulates the interrupts from another thread, which is the only
    arrangement where a blocking wait behaves differently from a polled one.

    `_thread.interrupt_main` sets the interpreter's interrupt flag rather than sending a
    signal, so the flag is only observed when the main thread runs bytecode -- deferred
    indefinitely inside a blocking `wait()`, seen within one poll interval otherwise. That is
    also why the child never receives a real SIGINT here, which conveniently models the
    "child ignores the first interrupt" case on every platform.
    """
    interrupter = threading.Thread(
        target=lambda: (
            time.sleep(1.0),
            _thread_interrupt(),
            time.sleep(1.5),
            _thread_interrupt(),
        ),
        daemon=True,
    )
    started = time.monotonic()
    interrupter.start()
    outcome = backend.run_backend([sys.executable, "-c", _DEAF_CHILD])
    elapsed = time.monotonic() - started
    captured = capfd.readouterr()
    # The child sleeps 30s and ignores SIGINT, so finishing quickly can only mean the second
    # interrupt was delivered mid-run and `terminate()` ran.
    assert elapsed < 20, f"escalation never reached the child ({elapsed:.1f}s)"
    assert "press Ctrl-C again" in captured.err
    assert "terminating sleap-nn" in captured.err
    assert outcome.exit_code != 0


def _thread_interrupt():
    """Raise ``KeyboardInterrupt`` in the main thread, as a console Ctrl-C does."""
    import _thread

    _thread.interrupt_main()


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


def test_staging_keeps_interpolations_unresolved_in_the_emitted_file(
    write_config, tmp_path, monkeypatch
):
    """The bytes that land on disk carry the interpolation, not the value behind it.

    `stage_artifacts` writes into the directory `registry/publish.py` uploads wholesale, so a
    resolved `${oc.env:...}` here is a secret published as a registry artifact. Asserted on the
    *file*, with the variable **set**: the unit test next to `to_sleap_nn_yaml` pins the string,
    this pins that nothing between it and the filesystem re-resolves.
    """
    monkeypatch.setenv("SLEAP_ROOTS_TEST_SECRET", "supersecret")
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {
                "ckpt_dir": str(tmp_path / "ckpt"),
                "run_name": "r1",
                "wandb": {"entity": "${oc.env:SLEAP_ROOTS_TEST_SECRET}"},
            }
        },
    )
    run_dir = backend.run_directory(cfg)
    destination = backend.emitted_config_path(run_dir, None)
    backend.stage_artifacts(cfg, source, run_dir, destination)
    staged = destination.read_bytes()
    assert b"${oc.env:SLEAP_ROOTS_TEST_SECRET}" in staged
    assert b"supersecret" not in staged


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
        # "fabricate", not "run": `="run"` is a substring of nearly every BackendError in the
        # module, so the test passed on any refusal rather than on the guard it is named for.
        with pytest.raises(backend.BackendError, match="fabricate"):
            backend.stage_artifacts(cfg, source, run_dir, run_dir / marker)
        # ...and nothing landed. Asserting only that an exception was raised is what let a
        # partial write leave a 0-byte marker behind unnoticed.
        assert not run_dir.exists() or not list(run_dir.iterdir())


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
    """A real probe, not a stub: this is the only record of the backend for an early death.

    Runs on Windows too. The `.bat` pattern beside it was added to the *failure* test only,
    so the success path -- the one asserting the reported version is the backend's real
    output -- skipped on `nt`, leaving the two reporting lines in `backend_version` uncovered
    there. Coverage on that leg was 99%, not the 100% previously reported.
    """
    if os.name == "nt":
        stub = tmp_path / "sleap-nn.bat"
        stub.write_text("@echo off\r\necho sleap-nn 9.9.9\r\n")
    else:
        stub = tmp_path / "sleap-nn"
        stub.write_text("#!/bin/sh\necho 'sleap-nn 9.9.9'\n", encoding="utf-8")
        stub.chmod(0o755)
    assert backend.backend_version(stub) == "sleap-nn 9.9.9"


def test_backend_version_is_a_diagnostic_and_never_a_gate(tmp_path):
    """A backend that cannot report a version still runs -- this must not raise."""
    assert backend.backend_version(tmp_path / "does_not_exist") is None


def test_a_wait_that_times_out_just_keeps_waiting(fake_popen):
    """The poll branch is a loop, not a failure: a long run times out thousands of times."""
    fake_popen.statuses = [
        subprocess.TimeoutExpired(cmd="sleap-nn", timeout=0.5),
        subprocess.TimeoutExpired(cmd="sleap-nn", timeout=0.5),
        0,
    ]
    outcome = backend.run_backend(["sleap-nn"])
    (call,) = fake_popen.instances
    assert outcome.exit_code == 0
    assert call.waits == 3
    assert not call.terminated and not call.killed


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


# --- review round 4: case-folding and ancestor walking ------------------------------------


@pytest.mark.parametrize("marker", backend.RUN_EVIDENCE)
@pytest.mark.parametrize("case", [str.lower, str.upper, str.capitalize])
def test_an_override_naming_run_evidence_in_any_case_is_refused(
    write_config, tmp_path, marker, case
):
    """NTFS is case-insensitive, so `Best.ckpt` *is* the evidence file the guard reads.

    An exact string match let `--resolved-config <run_dir>/Best.ckpt` write the guard's own
    marker, which then refused the directory forever -- with no `--force`, recovery would mean
    deleting files by hand.
    """
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError, match="fabricate"):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / case(marker))
    assert not run_dir.exists() or not list(run_dir.iterdir())


def test_an_override_inside_a_finished_runs_subtree_is_refused(write_config, tmp_path):
    """`add_dir` is recursive, so a nested file is published with that run's artifact.

    The guard looked one level up only, so `ckpt/otherrun/sub/emitted.yaml` slipped through
    while `ckpt/otherrun/emitted.yaml` was refused.
    """
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    other = tmp_path / "ckpt" / "otherrun"
    (other / "sub").mkdir(parents=True)
    (other / "best.ckpt").write_bytes(b"weights")
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError, match="previous run"):
        backend.stage_artifacts(cfg, source, run_dir, other / "sub" / "emitted.yaml")


def test_an_override_outside_the_checkpoint_tree_is_still_allowed(
    write_config, tmp_path
):
    """The ancestor walk is bounded: staging somewhere unrelated stays legal."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    elsewhere = tmp_path / "elsewhere" / "emitted.yaml"
    backend.stage_artifacts(cfg, source, run_dir, elsewhere)
    assert elsewhere.is_file()


def test_a_failed_version_probe_is_not_reported_as_a_version(tmp_path):
    """A non-zero probe used to echo its own usage text *as* the backend version.

    That matters because the echo is the substitute for stamping the version into a file, so a
    garbage string there is worse than saying nothing.
    """
    if os.name == "nt":
        stub = tmp_path / "sleap-nn.bat"
        stub.write_text(
            "@echo off\r\necho Error: No such option: --version\r\nexit /b 2\r\n"
        )
    else:
        stub = tmp_path / "sleap-nn"
        stub.write_text(
            "#!/bin/sh\necho 'Error: No such option: --version'\nexit 2\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
    assert backend.backend_version(stub) is None


# --- review round 5: the staging property, asserted after the writes -----------------------


def _staging_fixture(write_config, tmp_path):
    """A loaded config, its path, and the run directory `run` would train into."""
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(tmp_path / "ckpt"), "run_name": "r1"}
        },
    )
    return cfg, source, backend.run_directory(cfg)


@pytest.mark.parametrize(
    "spelling",
    sorted(
        set(_destination_spellings((*backend.RUN_EVIDENCE, backend.SOURCE_CONFIG_NAME)))
    ),
)
def test_staging_leaves_no_fabricated_evidence_and_an_intact_source_copy(
    write_config, tmp_path, spelling
):
    """The property, asserted **after** the writes, for every generated spelling.

    Four rounds of this bug were the same shape with a different spelling -- `C:foo`, `..`, a
    trailing dot, a case variant, Win32 mangling -- because the guard compared the string it
    was handed while the filesystem created a different one. A longer blocklist cannot win
    that race; the mangling rules belong to the OS.

    So this asserts neither a refusal nor a message. Each spelling is allowed to be refused
    *or* to succeed, and in **both** cases two things must hold afterwards:

    1. nothing in the run directory is a name the reuse check would read as a completed run --
       `run` must not be able to fabricate the evidence it later refuses, with no `--force`;
    2. `source_config.yaml`, if it exists, is byte-identical to the input -- it is the only
       artifact carrying the `experiment` block, so a write landing on top of it destroys
       species / mode / root_type / dataset identity at exit 0.

    A spelling nobody thought of fails this by violating an invariant, not by being missing
    from a list.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    source_bytes = source.read_bytes()
    folded_evidence = {_mangled(marker) for marker in backend.RUN_EVIDENCE}
    try:
        backend.stage_artifacts(cfg, source, run_dir, run_dir / spelling)
    except backend.BackendError:
        pass  # refusing is one correct outcome; leaving a lie behind is not
    landed = set(os.listdir(run_dir)) if run_dir.is_dir() else set()
    assert not [name for name in landed if _mangled(name) in folded_evidence], landed
    copy = run_dir / backend.SOURCE_CONFIG_NAME
    if copy.exists():
        assert copy.read_bytes() == source_bytes


def test_the_destination_that_destroys_the_source_copy_is_refused(
    write_config, tmp_path
):
    """The worst spelling, called out on its own so a regression names itself.

    `--emitted-config <run_dir>/source_config.yaml.` used to exit 0 with the trailing dot
    stripped at write time, leaving a file *named* `source_config.yaml` holding the
    experiment-stripped config -- and the success line asserting the run directory held it.
    The collision guard could not see it because `resolve()` cannot canonicalize a file that
    does not exist yet, and `source_config.yaml` is written *after* the check.

    The post-condition is the **property**, not the mechanism: whether the pre-write name
    check refused it or the post-write check caught and repaired it, what must not exist is a
    `source_config.yaml` that is not the operator's bytes. Asserting "the file is absent"
    would pass on POSIX (nothing is mangled, so the name check fires) and fail on Windows
    (where the repair restores it) -- a test that only holds on the host that cannot
    reproduce the bug.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(
            cfg, source, run_dir, run_dir / (backend.SOURCE_CONFIG_NAME + ".")
        )
    copy = run_dir / backend.SOURCE_CONFIG_NAME
    assert not copy.exists() or copy.read_bytes() == source.read_bytes()


@pytest.fixture
def win32_name_mangling(monkeypatch):
    """Make writes strip trailing dots and spaces the way Win32 does, on any host.

    That stripping happens in the OS at *creation* time and is the entire mechanism behind
    this round's findings -- which means three of the six matrix cells physically cannot
    reproduce them, and the post-write property check is shadowed on those cells by the
    pre-write name check that happens to fire first. Modelling the rule at the one seam that
    touches the filesystem makes every cell exercise the hazard, and makes the layer that is
    the actual guarantee testable rather than merely present.
    """
    real_write = backend._atomic_write

    def mangling_write(path, payload):
        return real_write(path.parent / (path.name.rstrip(". ") or path.name), payload)

    monkeypatch.setattr(backend, "_atomic_write", mangling_write)


@pytest.mark.parametrize(
    "spelling",
    [
        "source_config.yaml.",
        "source_config.yaml ",
        "source_config.yaml. ",
        "best.ckpt.",
        "best.ckpt ",
        "training_config.yaml ",
        "training_config.yaml..",
    ],
)
def test_a_mangling_filesystem_cannot_be_made_to_produce_a_lie(
    write_config, tmp_path, win32_name_mangling, spelling
):
    """The B1-B3 mechanism, driven on every platform rather than only the one that trains.

    With the filesystem stripping trailing dots and spaces, the guard compares one string
    while a different file is created. Neither refusal nor success is asserted -- only that
    afterwards the run directory holds no fabricated run evidence, and no `source_config.yaml`
    that is not the operator's bytes.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    source_bytes = source.read_bytes()
    folded_evidence = {_mangled(marker) for marker in backend.RUN_EVIDENCE}
    try:
        backend.stage_artifacts(cfg, source, run_dir, run_dir / spelling)
    except backend.BackendError:
        pass
    landed = set(os.listdir(run_dir)) if run_dir.is_dir() else set()
    assert not [name for name in landed if _mangled(name) in folded_evidence], landed
    copy = run_dir / backend.SOURCE_CONFIG_NAME
    if copy.exists():
        assert copy.read_bytes() == source_bytes


@pytest.fixture
def unmodelled_name_mangling(monkeypatch):
    """A filesystem aliasing rule this module does **not** know about.

    The reason for reading the directory back after the writes is that doing so does not
    require knowing the rule. Win32's trailing-dot stripping is now modelled by a guard *and*
    by a fixture, so a test using it cannot tell whether the post-write check is wired into
    `stage_artifacts` at all -- the pre-write name check fires first and the mutation survives.

    So this invents one: a trailing underscore is dropped at creation time. No guard in the
    module models it, and none should; that is the point. If the property is genuinely closed
    rather than enumerated, an unknown rule changes nothing.
    """
    real_write = backend._atomic_write

    def mangling_write(path, payload):
        return real_write(path.parent / (path.name.rstrip("_") or path.name), payload)

    monkeypatch.setattr(backend, "_atomic_write", mangling_write)


@pytest.mark.parametrize("spelling", ["best.ckpt_", "training_config.yaml_"])
def test_an_aliasing_rule_the_module_does_not_model_cannot_fabricate_evidence(
    write_config, tmp_path, unmodelled_name_mangling, spelling
):
    """The whole argument for the post-write check, stated as a test.

    Four rounds enumerated shapes and lost the race four times. This one is a shape the code
    has never heard of, and it is refused anyway -- with the fabricated file removed, so the
    run name is not bricked.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError, match="reuse check"):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / spelling)
    assert not [
        name
        for name in os.listdir(run_dir)
        if _mangled(name) in {_mangled(m) for m in backend.RUN_EVIDENCE}
    ]
    backend.check_run_directory(run_dir)


def test_an_aliasing_rule_the_module_does_not_model_cannot_destroy_the_source_copy(
    write_config, tmp_path, unmodelled_name_mangling
):
    """The same argument for the irreplaceable half: identity survives an unknown rule."""
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError, match="experiment block"):
        backend.stage_artifacts(
            cfg, source, run_dir, run_dir / (backend.SOURCE_CONFIG_NAME + "_")
        )
    assert (run_dir / backend.SOURCE_CONFIG_NAME).read_bytes() == source.read_bytes()


def test_evidence_that_cannot_be_removed_is_named_in_the_error(
    write_config, tmp_path, monkeypatch
):
    """A purge that fails must say so: that directory is bricked until someone deletes it.

    There is no `--force`, so "we tried and could not" is the operator's only signal that hand
    intervention is required.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    before = set(os.listdir(run_dir))
    source_bytes = source.read_bytes()
    (run_dir / backend.SOURCE_CONFIG_NAME).write_bytes(source_bytes)
    (run_dir / "best.ckpt").write_bytes(b"")

    def refuse_unlink(self, *args, **kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "unlink", refuse_unlink)
    with pytest.raises(backend.BackendError, match="could NOT remove"):
        backend._verify_staging(
            run_dir, run_dir / backend.SOURCE_CONFIG_NAME, source_bytes, before
        )


def test_a_destination_symlinked_onto_the_source_copy_is_refused(
    write_config, tmp_path
):
    """The name check cannot see this one: the basename is innocent, the target is not.

    A symlink is why the resolved-path collision guard stays even though the mangled-name
    check subsumes every *spelling* of `source_config.yaml`.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    link = elsewhere / "emitted.yaml"
    try:
        link.symlink_to(run_dir / backend.SOURCE_CONFIG_NAME)
    except (OSError, NotImplementedError) as error:  # pragma: no cover - host policy
        pytest.skip(f"this host does not allow creating symlinks: {error}")
    with pytest.raises(backend.BackendError, match="which `run` writes itself"):
        backend.stage_artifacts(cfg, source, run_dir, link)


def test_a_metadata_write_failure_is_a_clean_error(write_config, tmp_path, monkeypatch):
    """The sidecar is written after the configs, so its failure needs its own message."""
    cfg, _source, run_dir = _staging_fixture(write_config, tmp_path)
    run_dir.mkdir(parents=True, exist_ok=True)

    def failing_write(path, payload):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(backend, "_atomic_write", failing_write)
    with pytest.raises(backend.BackendError, match="run's metadata"):
        backend.stage_run_metadata(run_dir, tmp_path / "bin" / "sleap-nn", "0.2.0")


def test_the_post_write_check_catches_evidence_it_did_not_predict(
    write_config, tmp_path
):
    """The guarantee layer, pinned on its own rather than through a spelling.

    `_verify_staging` is what makes this family closed instead of enumerated, so it is driven
    against a run directory put into the bad state directly -- no destination string involved,
    and therefore nothing for a future mangling rule to route around.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    before = set(os.listdir(run_dir))
    source_bytes = source.read_bytes()
    (run_dir / backend.SOURCE_CONFIG_NAME).write_bytes(source_bytes)
    (run_dir / "best.ckpt").write_bytes(b"")
    with pytest.raises(backend.BackendError, match="reuse check"):
        backend._verify_staging(
            run_dir, run_dir / backend.SOURCE_CONFIG_NAME, source_bytes, before
        )
    assert not (run_dir / "best.ckpt").exists()  # repaired, not merely reported
    backend.check_run_directory(run_dir)  # ...so the run name is not bricked


def test_the_post_write_check_restores_a_rewritten_source_copy(write_config, tmp_path):
    """The other half of the guarantee: the irreplaceable artifact is put back.

    Losing it is silent -- the emitted config has the `experiment` block stripped, so what
    remains is a plausible file recording no species, mode, root type or dataset.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    before = set(os.listdir(run_dir))
    source_bytes = source.read_bytes()
    copy = run_dir / backend.SOURCE_CONFIG_NAME
    copy.write_bytes(b"the emitted config, with the experiment block stripped\n")
    with pytest.raises(backend.BackendError, match="experiment block"):
        backend._verify_staging(run_dir, copy, source_bytes, before)
    assert copy.read_bytes() == source_bytes


def test_a_write_that_materializes_evidence_before_failing_leaves_none_behind(
    write_config, tmp_path, monkeypatch
):
    """B3's filesystem effect, driven directly so it is exercised on every host.

    On NTFS, `--emitted-config <run_dir>/best.ckpt:x` makes `mkstemp` materialize the **base**
    file `best.ckpt` (`:` opens an alternate data stream); `os.replace` then fails and
    `_atomic_write`'s `except BaseException` can only unlink the temp stream, leaving a 0-byte
    `best.ckpt` that bricks the run name forever. The `:` is refused by name now, so this
    stubs the same effect: whatever a *failed* write leaves behind, it must not be something
    the reuse check reads as a completed run.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    real_write = backend._atomic_write

    def hostile_write(path, payload):
        if path.name == backend.SOURCE_CONFIG_NAME:
            return real_write(path, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "best.ckpt").write_bytes(b"")  # what mkstemp does on NTFS
        raise OSError(87, "The parameter is incorrect")

    monkeypatch.setattr(backend, "_atomic_write", hostile_write)
    with pytest.raises(backend.BackendError, match="could not write"):
        backend.stage_artifacts(
            cfg, source, run_dir, run_dir / backend.EMITTED_CONFIG_NAME
        )
    assert not (run_dir / "best.ckpt").exists()
    # ...and the run name is not bricked: a retry must still be possible without --force.
    backend.check_run_directory(run_dir)


@pytest.mark.parametrize(
    "name", ["CON", "NUL", "aux.yaml", "a?b.yaml", "best.ckpt:x", 'q"uote.yaml']
)
def test_the_destination_basename_gets_run_names_portability_rules(
    write_config, tmp_path, name
):
    """`--emitted-config` was the only path input in the module with no portability check.

    `<run_dir>/CON` exited 0 with argv pointing at a console device; `NUL` and `a?b.yaml`
    surfaced as write failures blaming the write rather than the name. `run_name` refuses all
    of these on *every* platform with the explicit reasoning that a Mac-authored config must
    not fail only on the box that trains -- the same reasoning, the same rules.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError, match="--emitted-config"):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / name)


def test_the_run_metadata_sidecar_is_also_guarded_against_the_override(
    write_config, tmp_path
):
    """`run` writes it, so `--emitted-config` must not be able to land on top of it."""
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError, match="--emitted-config"):
        backend.stage_artifacts(
            cfg, source, run_dir, run_dir / backend.RUN_METADATA_NAME
        )


def test_an_empty_destination_says_what_is_actually_wrong(write_config, tmp_path):
    """`--emitted-config ''` reported "must not name a file, but . is a directory"."""
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError, match="--emitted-config"):
        backend.stage_artifacts(cfg, source, run_dir, Path(""))


def test_a_case_variant_of_the_source_copy_is_refused_on_a_folding_filesystem(
    write_config, tmp_path
):
    """`PosixPath.__eq__` is case-sensitive; macOS ships case-insensitive APFS.

    The two `Path.__eq__` collision guards were safe on Windows only because
    `WindowsPath.__eq__` folds case -- making them the one rule in the module that answers
    differently per host, which is what its own comments argue against.
    """
    cfg, source, run_dir = _staging_fixture(write_config, tmp_path)
    with pytest.raises(backend.BackendError):
        backend.stage_artifacts(cfg, source, run_dir, run_dir / "Source_Config.YAML")


def test_every_accepted_run_name_lands_strictly_inside_ckpt_dir(tmp_path):
    """The containment invariant over *generated* names rather than an enumerated list.

    Deliberately one-directional: this says nothing about which names must be refused -- that
    is the refusal tests' job, and repeating it here would be the same blocklist in another
    file. It says that **whatever** the accept/reject rule turns out to be, no accepted name
    can put the run directory anywhere but immediately inside the resolved `ckpt_dir`. A new
    escape shape fails this without anyone having thought of it.
    """
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    accepted = 0
    for run_name in _generated_run_names():
        cfg = OmegaConf.create(
            {"trainer_config": {"ckpt_dir": str(ckpt), "run_name": run_name}}
        )
        try:
            run_dir = backend.run_directory(cfg)
        except backend.BackendError:
            continue
        accepted += 1
        assert run_dir.resolve().parent == ckpt.resolve(), run_name
        assert ckpt.resolve() in run_dir.resolve().parents, run_name
    # Without this the invariant would be satisfied by refusing everything.
    assert (
        accepted
    ), "the generator produced no accepted name; the assertion was vacuous"


@pytest.mark.parametrize(
    "run_name", ["run\u200bname", "run\u202ename", "run\ufeffname"]
)
def test_a_run_name_with_invisible_formatting_characters_is_refused(
    write_config, run_name
):
    """Two names that render identically would be two directories -- and a W&B run id.

    `run_name` already refuses control characters below 32; Unicode category `Cf` is the same
    hazard with no visual signal at all.
    """
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"run_name": run_name}})
    with pytest.raises(backend.BackendError, match="trainer_config.run_name"):
        backend.run_directory(cfg)


# --- review round 5: what counts as a run, and how far the ancestor walk reaches ---------


def test_a_run_that_died_after_the_trainer_was_built_is_not_overwritten(tmp_path):
    """`RUN_EVIDENCE` held only *completion* markers, so a crashed run read as a clean slate.

    `best.ckpt` and `training_config.yaml` are both written at or after success. sleap-nn
    writes `initial_config.yaml` at trainer-construction time (this change's own design.md
    records it), so a run that reached construction and then died -- an OOM at epoch 5, a CUDA
    fault -- leaves a directory the guard called empty, and a retry silently overwrote the
    only record of what that run was going to train.
    """
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "initial_config.yaml").write_text("model_config: {}\n", encoding="utf-8")
    with pytest.raises(backend.BackendError, match="previous run"):
        backend.check_run_directory(run_dir)


def test_a_directory_holding_only_this_commands_own_artifacts_is_still_the_retry_case(
    tmp_path,
):
    """The retry path must survive the widening above.

    A run that died *before* the backend built anything leaves only what `run` itself wrote,
    and those are regenerated from the same input -- no flag should be needed.
    """
    run_dir = tmp_path / "ckpt" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / backend.EMITTED_CONFIG_NAME).write_text("stale", encoding="utf-8")
    (run_dir / backend.SOURCE_CONFIG_NAME).write_text("stale", encoding="utf-8")
    backend.check_run_directory(run_dir)  # must not raise


def test_a_checkpoint_directory_that_is_itself_a_finished_run_is_refused(
    write_config, tmp_path
):
    """`ckpt_dir` was never checked, and `ckpt_dir: models/baseline_v1` is an ordinary typo.

    With evidence sitting in `ckpt/`, a plain `run` with no override exited 0 and wrote into
    that finished run's tree -- which a recursive `add_dir` then publishes.
    """
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "best.ckpt").write_bytes(b"weights")
    cfg, source = _cfg(
        write_config,
        overrides={"trainer_config": {"ckpt_dir": str(ckpt), "run_name": "r1"}},
    )
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError, match="previous run"):
        backend.stage_artifacts(
            cfg, source, run_dir, run_dir / backend.EMITTED_CONFIG_NAME
        )


def test_a_destination_deep_inside_a_finished_run_outside_ckpt_dir_is_refused(
    write_config, tmp_path
):
    """The walk refused depth 1 outside the boundary but accepted depth 2.

    The realistic shape is `ckpt_dir: models_scratch` while the published baseline lives under
    `models/` -- and `add_dir` is recursive regardless of which `ckpt_dir` a run belongs to,
    which is the whole rationale for walking ancestors at all.
    """
    finished = tmp_path / "models" / "baseline_v1"
    (finished / "sub").mkdir(parents=True)
    (finished / "best.ckpt").write_bytes(b"weights")
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {
                "ckpt_dir": str(tmp_path / "models_scratch"),
                "run_name": "r1",
            }
        },
    )
    run_dir = backend.run_directory(cfg)
    with pytest.raises(backend.BackendError, match="previous run"):
        backend.stage_artifacts(cfg, source, run_dir, finished / "sub" / "emitted.yaml")


def test_the_ancestor_walk_stops_at_the_operators_own_configuration(
    write_config, tmp_path, monkeypatch
):
    """The walk is bounded, and bounded by something the operator controls.

    Anything at or above the deepest directory the destination and `ckpt_dir` share is out of
    scope: a stray `training_config.yaml` in a home directory or a repo root must not refuse
    every run underneath it, since there is no `--force` and the operator may not own it.
    """
    root = tmp_path / "workspace"
    (root / "ckpt").mkdir(parents=True)
    (root / "elsewhere").mkdir()
    (tmp_path / "training_config.yaml").write_text("stray", encoding="utf-8")
    monkeypatch.chdir(root)
    cfg, source = _cfg(
        write_config,
        overrides={
            "trainer_config": {"ckpt_dir": str(root / "ckpt"), "run_name": "r1"}
        },
    )
    run_dir = backend.run_directory(cfg)
    backend.stage_artifacts(cfg, source, run_dir, root / "elsewhere" / "emitted.yaml")
    assert (root / "elsewhere" / "emitted.yaml").is_file()


@pytest.mark.parametrize("ckpt_dir", ["C:foo", "models ", "models."])
def test_ckpt_dir_gets_the_same_portability_rules_as_run_name(write_config, ckpt_dir):
    """The field supplying the left-hand side of every guarded path took neither check.

    `_check_single_component` explains at length why `C:foo` and a trailing dot or space are
    unsafe; applying that reasoning to only one of the two fields was the asymmetry.
    """
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"ckpt_dir": ckpt_dir}})
    with pytest.raises(backend.BackendError, match="trainer_config.ckpt_dir"):
        backend.run_directory(cfg)


@pytest.mark.parametrize(
    "ckpt_dir", ["models", "models/nested", "../sibling", "/tmp/abs"]
)
def test_ordinary_checkpoint_directories_are_still_accepted(write_config, ckpt_dir):
    """`ckpt_dir` is a *path*, not a single component -- separators stay legal."""
    cfg, _ = _cfg(write_config, overrides={"trainer_config": {"ckpt_dir": ckpt_dir}})
    assert backend.run_directory(cfg).parent == Path(ckpt_dir)
