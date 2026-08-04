"""Shared pytest fixtures for the sleap-roots-training test suite.

Centralizes the setup that was otherwise re-invented across test modules — writing a
selection-matrix YAML to a temp path, staging a stub models-root, and isolating the
wandb/registry environment (env vars + netrc/home) for hermetic tests — plus loaders for
the committed TensorFlow-reference W&B payloads under ``tests/fixtures/tf_reference/``.
"""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Callable

import pytest
from omegaconf import OmegaConf

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

#: The wandb/registry environment variables a hermetic test must clear. ``NETRC`` joins
#: the registry vars so netrc-based credential resolution is isolated too; ``HOME``/
#: ``USERPROFILE`` are *repointed* (not cleared) by ``isolate_wandb_env`` below.
_WANDB_ENV_VARS = (
    "WANDB_API_KEY",
    "WANDB_ENTITY",
    "SLEAP_ROOTS_MODEL_REGISTRY",
    "SLEAP_ROOTS_MODEL_ALIAS",
    "NETRC",
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


#: A 16x16 grayscale JPEG, committed as bytes rather than generated.
#:
#: The labeling builder opens curated images through sleap-io's ``ImageVideo`` backend,
#: which decodes them, so its fixtures need real JPEGs rather than placeholder bytes.
#: Writing them with ``imageio`` would make the tests depend on a package that is only
#: importable *transitively* via sleap-io — the same trap task 2.1 closed for ``pandas``,
#: and not worth a direct test dependency for 447 bytes of constant.
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAAQABABAREA/8QAHwAAAQUBAQEB"
    "AQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1Fh"
    "ByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZ"
    "WmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oACAEBAAA/APMfAfgP/hN/7Q/4mX2L"
    "7H5f/LDzN+/d/tDGNv60ePPAf/CEf2f/AMTL7b9s8z/lh5ezZt/2jnO79KPAfjz/AIQj+0P+Jb9t"
    "+2eX/wAt/L2bN3+yc53fpR488ef8Jv8A2f8A8S37F9j8z/lv5m/ft/2RjG39a//Z"
)


def write_jpeg(path: Path) -> Path:
    """Write :data:`TINY_JPEG` to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(TINY_JPEG)
    return path


@pytest.fixture
def tiny_matrix(tmp_path: Path) -> Path:
    """Write the minimal selection matrix to a temp path and return it."""
    path = tmp_path / "matrix.yaml"
    path.write_text(TINY_MATRIX, encoding="utf-8")
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
def isolate_wandb_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Fully isolate wandb/registry credential resolution from the host environment.

    Clears every var in ``_WANDB_ENV_VARS`` (``WANDB_API_KEY``/``WANDB_ENTITY``/the two
    ``SLEAP_ROOTS_MODEL_*`` vars/``NETRC``) and repoints ``HOME``/``USERPROFILE`` at an
    empty temp dir, so neither an exported key, an ambient ``wandb login`` netrc, nor a
    stray registry override leaks in — on any OS.

    Returns:
        The isolated home dir, so a test can write ``.netrc``/``_netrc`` into it to
        exercise the netrc fallback branches. Tests that need the underlying
        ``monkeypatch`` (e.g. to layer further patches) can request it as a separate
        fixture param — pytest hands this fixture and the test the same instance.
    """
    home = tmp_path / "home"
    home.mkdir()
    for var in _WANDB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def tf_reference_dir() -> Path:
    """The directory of committed TensorFlow-reference W&B payload fixtures."""
    return FIXTURES_DIR / "tf_reference"


#: A canonical, fully-valid training config reused across the config + CLI tests. It is
#: *final*-valid on purpose — a valid ``experiment`` vocab, an integer ``trainer_config.seed``,
#: a backbone + head (so it also passes deep sleap-nn validation under ``[train]``), and
#: ``use_wandb`` absent (so no W&B target is required) — so that adding the seed and W&B
#: checks in later commits never turns an earlier group's "good" config red. Tests state only
#: their *deviation* from it via ``write_config(overrides=..., drop=...)``.
VALID_CONFIG: dict = {
    "experiment": {
        "species": "arabidopsis",
        "mode": "cylinder",
        "root_type": "primary",
        "dataset": {
            "name": "arabidopsis_primary_cylinder",
            "path": "data/train.pkg.slp",
            "notes": "Tier 1 baseline dataset",
        },
    },
    "data_config": {
        "train_labels_path": ["data/train.pkg.slp"],
        "val_labels_path": ["data/val.pkg.slp"],
        "preprocessing": {
            "ensure_rgb": False,
            "ensure_grayscale": False,
            "max_height": 192,
            "max_width": 192,
            "scale": 1.0,
        },
    },
    "model_config": {
        "backbone_config": {"unet": {"filters": 32, "max_stride": 16}},
        "head_configs": {"single_instance": {"confmaps": {"sigma": 5.0}}},
    },
    "trainer_config": {
        "max_epochs": 50,
        "seed": 42,
        "save_ckpt": True,
        "ckpt_dir": "models",
        "run_name": "arabidopsis_primary_cylinder",
    },
}


def _drop_key(cfg: OmegaConf, dotted: str) -> None:
    """Delete a dotted key (e.g. ``trainer_config.seed``) from an OmegaConf container."""
    parts = dotted.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]


@pytest.fixture
def write_config(tmp_path: Path) -> Callable[..., Path]:
    """Return a factory that writes a training-config YAML to a temp path and returns it.

    The factory starts from a deep copy of ``VALID_CONFIG`` so a test only states its
    deviation:

    - ``overrides``: an OmegaConf-mergeable mapping deep-merged onto the valid config
      (set a value, or add an unknown key to exercise rejection).
    - ``drop``: dotted keys to delete (e.g. ``"experiment"`` or ``"trainer_config.seed"``).

    Fixtures are self-contained (built in ``tmp_path``); tests never read ``examples/``.
    """

    def _write(
        name: str = "config.yaml",
        overrides: dict | None = None,
        drop: tuple[str, ...] = (),
    ) -> Path:
        cfg = OmegaConf.create(copy.deepcopy(VALID_CONFIG))
        if overrides:
            cfg = OmegaConf.merge(cfg, overrides)
        for dotted in drop:
            _drop_key(cfg, dotted)
        path = tmp_path / name
        path.write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def tf_config(tf_reference_dir: Path) -> Callable[[str], dict]:
    """Return a loader for a committed run ``config`` payload by run id."""

    def load(run_id: str) -> dict:
        path = tf_reference_dir / f"{run_id}.config.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return load


@pytest.fixture
def tf_summary(tf_reference_dir: Path) -> Callable[[str], dict]:
    """Return a loader for a committed run ``summary`` payload by run id."""

    def load(run_id: str) -> dict:
        path = tf_reference_dir / f"{run_id}.summary.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return load
