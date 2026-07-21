"""Shared pytest fixtures for the sleap-roots-training test suite.

Centralizes the setup that was otherwise re-invented across test modules — writing a
selection-matrix YAML to a temp path, staging a stub models-root, and clearing the
wandb/registry environment for hermetic tests — plus loaders for the committed
TensorFlow-reference W&B payloads under ``tests/fixtures/tf_reference/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

#: Directory holding committed test data.
FIXTURES_DIR = Path(__file__).parent / "fixtures"

#: The seven canonical run ids of the TensorFlow-reference receptive-field sweep, in
#: stride order. Single source of truth for the tests that key off them (the standalone
#: capture script keeps its own copy, guarded against drift by ``test_tf_reference``).
TF_RUN_IDS = (
    "ijn85j6w",  # stride 8  (no summary metrics)
    "nxe8xgsd",  # stride 16
    "v7rdm7cd",  # stride 16
    "qilbptpp",  # stride 32
    "1tryadtu",  # stride 32
    "yenwgpjq",  # stride 64
    "26ryyfu2",  # stride 64 (no summary metrics)
)

#: The runs that logged no summary metrics (only the ``_wandb`` bookkeeping key).
NO_SUMMARY_RUNS = frozenset({"ijn85j6w", "26ryyfu2"})

#: The wandb/registry environment variables a hermetic registry test must clear.
_WANDB_ENV_VARS = (
    "WANDB_API_KEY",
    "WANDB_ENTITY",
    "SLEAP_ROOTS_MODEL_REGISTRY",
    "SLEAP_ROOTS_MODEL_ALIAS",
)

#: A minimal one-row selection matrix (one primary + one lateral, shared checksum).
TINY_MATRIX = """\
models:
  - species: soybean
    mode: cylinder
    age: "2, 3"
    primary_model_id: soy/p
    lateral_model_id: soy/l
    crown_model_id: null
checksums:
  soy/p: {sha}
  soy/l: {sha}
""".format(sha="0" * 64)


@pytest.fixture
def tiny_matrix(tmp_path: Path) -> Path:
    """Write the minimal selection matrix to a temp path and return it."""
    path = tmp_path / "matrix.yaml"
    path.write_text(TINY_MATRIX)
    return path


@pytest.fixture
def stub_models_root(tmp_path: Path) -> Path:
    """A models-root with the two tiny models as already-unzipped dirs."""
    root = tmp_path / "models"
    for model_id in ("soy/p", "soy/l"):
        model_dir = root / model_id
        model_dir.mkdir(parents=True)
        (model_dir / "best_model.h5").write_bytes(b"w")
        (model_dir / "training_config.json").write_bytes(b"{}")
    return root


@pytest.fixture
def clean_wandb_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Delete every wandb/registry env var so registry tests are hermetic.

    Returns the ``monkeypatch`` instance so the test can layer further patches on it.
    """
    for var in _WANDB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def tf_reference_dir() -> Path:
    """The directory of committed TensorFlow-reference W&B payload fixtures."""
    return FIXTURES_DIR / "tf_reference"


@pytest.fixture
def tf_config(tf_reference_dir: Path) -> Callable[[str], dict]:
    """Return a loader for a committed run ``config`` payload by run id."""

    def load(run_id: str) -> dict:
        return json.loads((tf_reference_dir / f"{run_id}.config.json").read_text())

    return load


@pytest.fixture
def tf_summary(tf_reference_dir: Path) -> Callable[[str], dict]:
    """Return a loader for a committed run ``summary`` payload by run id."""

    def load(run_id: str) -> dict:
        return json.loads((tf_reference_dir / f"{run_id}.summary.json").read_text())

    return load
