"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

_WANDB_CRED_ENV_VARS = ("WANDB_API_KEY", "NETRC")


@pytest.fixture
def isolate_netrc(monkeypatch, tmp_path) -> Path:
    """Isolate wandb credential resolution from the host environment.

    Clears ``WANDB_API_KEY``/``NETRC`` and points ``HOME``/``USERPROFILE`` at an
    empty temp dir so tests never pick up an ambient credential (e.g. a
    developer who has run ``wandb login``) and behave identically on every OS.

    Returns:
        The isolated home directory, so tests can write ``.netrc``/``_netrc``
        into it to exercise the fallback branches.
    """
    home = tmp_path / "home"
    home.mkdir()
    for name in _WANDB_CRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home
