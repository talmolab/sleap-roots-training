"""Base-install-safe unit tests for the training-config wrapper.

These exercise only the surface that works without the optional ``train`` extra —
loading, experiment-metadata validation, the explicit-seed check, the W&B-enablement
pairing check, and the deep-validation *skip* behavior — using OmegaConf alone. The deep
sleap-nn delegation (backbone/head must-be-set, ``preprocessing`` materialization) is
covered in ``test_config_integration.py`` (``@pytest.mark.integration``), since ``sleap_nn``
lives in the ``train`` extra CI never installs.

An autouse fixture forces the base-safe path so these stay deterministic even on a box
where ``[train]`` *is* installed (otherwise ``validate_config`` would take the deep path).
"""

from __future__ import annotations

import sys

import pytest

from sleap_roots_training import config


@pytest.fixture(autouse=True)
def _force_base_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the no-``[train]`` path so base-safe assertions do not depend on the host."""
    monkeypatch.setattr(config, "_deep_validation_available", lambda: False)


# --- Composed schema + experiment metadata (Requirement 1) -----------------------------


def test_valid_config_loads_and_validates(write_config):
    path = write_config()
    cfg = config.load_config(path)
    notes = config.validate_config(cfg)
    assert cfg.experiment.species == "arabidopsis"
    assert isinstance(notes, list)


@pytest.mark.parametrize(
    "field, value",
    [("species", "banana"), ("mode", "spinny"), ("root_type", "tuber")],
)
def test_invalid_experiment_vocab_is_rejected(write_config, field, value):
    path = write_config(overrides={"experiment": {field: value}})
    with pytest.raises(config.ConfigError, match=field):
        config.validate_config(config.load_config(path))


def test_missing_experiment_block_is_rejected(write_config):
    path = write_config(drop=("experiment",))
    with pytest.raises(config.ConfigError, match="experiment"):
        config.validate_config(config.load_config(path))


def test_missing_required_experiment_field_is_rejected(write_config):
    path = write_config(drop=("experiment.species",))
    with pytest.raises(config.ConfigError, match="species"):
        config.validate_config(config.load_config(path))


def test_unknown_top_level_key_is_rejected(write_config):
    path = write_config(overrides={"trainer_confg": {"seed": 1}})
    with pytest.raises(config.ConfigError, match="trainer_confg"):
        config.validate_config(config.load_config(path))


# --- Load / parse errors (Requirement 2, malformed input) ------------------------------


def test_malformed_yaml_is_rejected_cleanly(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("experiment: [unbalanced\n", encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load_config(path)


def test_empty_config_is_rejected(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load_config(path)


# --- Reproducibility: explicit integer seed (Requirement 3) ----------------------------


def test_missing_seed_is_rejected(write_config):
    path = write_config(drop=("trainer_config.seed",))
    with pytest.raises(config.ConfigError, match="seed"):
        config.validate_config(config.load_config(path))


def test_null_seed_is_rejected(write_config):
    path = write_config(overrides={"trainer_config": {"seed": None}})
    with pytest.raises(config.ConfigError, match="seed"):
        config.validate_config(config.load_config(path))


def test_non_integer_seed_is_rejected(write_config):
    path = write_config(overrides={"trainer_config": {"seed": "forty-two"}})
    with pytest.raises(config.ConfigError, match="seed"):
        config.validate_config(config.load_config(path))


def test_integer_seed_passes(write_config):
    path = write_config(overrides={"trainer_config": {"seed": 7}})
    config.validate_config(config.load_config(path))  # must not raise


def test_missing_preprocessing_is_rejected(write_config):
    path = write_config(drop=("data_config.preprocessing",))
    with pytest.raises(config.ConfigError, match="preprocessing"):
        config.validate_config(config.load_config(path))


# --- Emit: the sleap-nn-native config (experiment stripped), base-safe -------------------


def test_to_sleap_nn_config_strips_experiment(write_config):
    emitted = config.to_sleap_nn_config(config.load_config(write_config()))
    assert "experiment" not in emitted
    for key in ("data_config", "model_config", "trainer_config"):
        assert key in emitted


def test_to_sleap_nn_yaml_has_no_experiment(write_config):
    text = config.to_sleap_nn_yaml(config.load_config(write_config()))
    assert "experiment" not in text
    assert "data_config" in text


# --- W&B enablement pairing (Requirement 4) --------------------------------------------


def test_use_wandb_true_without_target_is_rejected(write_config):
    path = write_config(overrides={"trainer_config": {"use_wandb": True}})
    with pytest.raises(config.ConfigError, match="wandb"):
        config.validate_config(config.load_config(path))


def test_use_wandb_true_with_target_passes(write_config):
    path = write_config(
        overrides={
            "trainer_config": {
                "use_wandb": True,
                "wandb": {"entity": "eberrigan", "project": "sleap-roots"},
            }
        }
    )
    config.validate_config(config.load_config(path))  # must not raise


def test_use_wandb_false_needs_no_target(write_config):
    path = write_config(overrides={"trainer_config": {"use_wandb": False}})
    config.validate_config(config.load_config(path))  # must not raise


def test_use_wandb_absent_needs_no_target(write_config):
    # VALID_CONFIG omits use_wandb entirely -> treated as false, no target required.
    config.validate_config(config.load_config(write_config()))  # must not raise


# --- Deep-validation gating: skip-note + import hygiene (Requirements 2 & lazy import) --


def test_skip_note_when_backend_absent(write_config):
    notes = config.validate_config(config.load_config(write_config()))
    assert any("train" in note.lower() for note in notes)


def test_skip_does_not_swallow_a_base_failure(write_config):
    path = write_config(drop=("trainer_config.seed",))
    with pytest.raises(config.ConfigError):
        config.validate_config(config.load_config(path))


def test_base_path_does_not_import_sleap_nn(write_config, monkeypatch):
    monkeypatch.delitem(sys.modules, "sleap_nn", raising=False)
    config.validate_config(config.load_config(write_config()))
    assert "sleap_nn" not in sys.modules


# --- Malformed / non-mapping blocks are reported cleanly, not as tracebacks -------------

_VALID_EXP = (
    "experiment: {species: arabidopsis, mode: cylinder, root_type: primary, "
    "dataset: {name: d, path: p}}\n"
)
# Experiment + a valid data_config so checks after _check_preprocessing (e.g. W&B) are reached.
_VALID_BASE = _VALID_EXP + (
    "data_config: {preprocessing: {ensure_rgb: false, ensure_grayscale: false, scale: 1.0}}\n"
)


def _write(tmp_path, body: str):
    path = tmp_path / "c.yaml"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "body",
    [
        "experiment: primary\ntrainer_config: {seed: 1}\n",  # scalar experiment
        "experiment: null\ntrainer_config: {seed: 1}\n",  # null experiment
        _VALID_EXP + "trainer_config:\n  - seed: 1\n",  # list-shaped trainer_config
        _VALID_EXP
        + "data_config: 5\ntrainer_config: {seed: 1}\n",  # scalar data_config
    ],
)
def test_non_mapping_block_is_rejected_cleanly(tmp_path, body):
    with pytest.raises(config.ConfigError, match="must be a mapping"):
        config.validate_config(config.load_config(_write(tmp_path, body)))


def test_top_level_list_is_rejected(tmp_path):
    with pytest.raises(config.ConfigError):
        config.load_config(_write(tmp_path, "- a\n- b\n"))


def test_list_shaped_wandb_is_rejected_cleanly(tmp_path):
    body = _VALID_BASE + "trainer_config: {seed: 1, use_wandb: true, wandb: [a, b]}\n"
    with pytest.raises(config.ConfigError, match="wandb must be a mapping"):
        config.validate_config(config.load_config(_write(tmp_path, body)))


def test_non_boolean_use_wandb_is_rejected(tmp_path):
    body = _VALID_BASE + 'trainer_config: {seed: 1, use_wandb: "false"}\n'
    with pytest.raises(config.ConfigError, match="use_wandb must be a boolean"):
        config.validate_config(config.load_config(_write(tmp_path, body)))


def test_wandb_partial_target_is_rejected(tmp_path):
    # entity present, project missing -> the per-key loop's second iteration must fire.
    body = (
        _VALID_BASE + "trainer_config: {seed: 1, use_wandb: true, wandb: {entity: e}}\n"
    )
    with pytest.raises(config.ConfigError, match="project"):
        config.validate_config(config.load_config(_write(tmp_path, body)))


# --- preprocessing shape (not just presence) + wandb-when-disabled + deep-import guard ---

_EXP_SEED = _VALID_EXP + "trainer_config: {seed: 1}\n"


@pytest.mark.parametrize(
    "preprocessing, match",
    [
        ("notadict", "must be a mapping"),  # scalar
        ("[]", "must be a mapping"),  # list
        ("{}", "missing required key"),  # empty mapping
        ("{max_height: 192}", "missing required key"),  # mapping missing the 0.2.0 keys
    ],
)
def test_malformed_preprocessing_is_rejected(tmp_path, preprocessing, match):
    body = _EXP_SEED + f"data_config: {{preprocessing: {preprocessing}}}\n"
    with pytest.raises(config.ConfigError, match=match):
        config.validate_config(config.load_config(_write(tmp_path, body)))


def test_list_shaped_wandb_rejected_even_when_use_wandb_absent(tmp_path):
    # No use_wandb key (defaults to false) + a malformed wandb block -> still rejected.
    body = _VALID_BASE + "trainer_config: {seed: 1, wandb: [a, b]}\n"
    with pytest.raises(config.ConfigError, match="wandb must be a mapping"):
        config.validate_config(config.load_config(_write(tmp_path, body)))


def test_whitespace_wandb_target_is_rejected(tmp_path):
    body = _VALID_BASE + (
        'trainer_config: {seed: 1, use_wandb: true, wandb: {entity: "  ", project: p}}\n'
    )
    with pytest.raises(config.ConfigError, match="entity"):
        config.validate_config(config.load_config(_write(tmp_path, body)))


def test_deep_validation_import_failure_is_clean(write_config, monkeypatch):
    # Force the deep path "available" but make the sleap_nn import fail -> a clean ConfigError,
    # not a raw ModuleNotFoundError leaking out.
    monkeypatch.setattr(config, "_deep_validation_available", lambda: True)

    def _boom():
        raise ImportError("simulated broken sleap_nn install")

    monkeypatch.setattr(config, "_import_sleap_nn", _boom)
    with pytest.raises(config.ConfigError, match="backend validation failed"):
        config.validate_config(config.load_config(write_config()))
