"""Tests for locating and driving the ``sleap-nn`` training backend.

Base-install safe: CI never installs the ``train`` extra, so nothing here executes the
real backend. Resolution is exercised against **stub** console scripts written into
``tmp_path``, and the interpreter-side lookup is driven through the
``backend._interpreter_scripts_dir`` seam.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from sleap_roots_training import backend


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
