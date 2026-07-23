"""Every shipped example config must pass base-safe validation.

Guards the ``examples/`` the training guide tells users to copy against rot — a broken
example (bad vocab, missing seed, unknown key) would fail here. Base-safe (forces the
no-``[train]`` path), so it runs on the normal CI matrix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sleap_roots_training import config

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
EXAMPLE_CONFIGS = sorted(EXAMPLES_DIR.glob("*.yaml"))


@pytest.fixture(autouse=True)
def _force_base_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_deep_validation_available", lambda: False)


def test_examples_dir_is_not_empty():
    assert EXAMPLE_CONFIGS, f"no example configs found under {EXAMPLES_DIR}"


@pytest.mark.parametrize("path", EXAMPLE_CONFIGS, ids=lambda p: p.name)
def test_example_config_passes_base_safe_validation(path: Path):
    config.validate_config(config.load_config(path))  # must not raise
