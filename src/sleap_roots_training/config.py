"""Typed, validated training configuration composed over sleap-nn's own config.

An experiment is a single YAML file: sleap-nn's native ``data_config`` / ``model_config`` /
``trainer_config`` (consumed as-is), plus a repo-owned ``experiment`` block carrying the
domain identity sleap-nn has no concept of (species / mode / root_type / dataset). This
module validates the ``experiment`` block itself and *delegates* validation of the sleap-nn
portion to sleap-nn's ``verify_training_cfg`` / ``TrainingJobConfig`` — it never re-declares
sleap-nn's fields.

Base-install safe: ``sleap_nn`` lives in the optional ``train`` extra and is imported
*lazily*, only for the deep-validation and config-emission paths. Loading, the experiment
metadata checks, the explicit-seed check, and the W&B-enablement pairing check all run with
OmegaConf alone, so ``validate`` works (partially, with a clear note) without the backend.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import yaml
from omegaconf import MISSING, DictConfig, OmegaConf
from omegaconf.errors import OmegaConfBaseException

from sleap_roots_training.registry.cards import _ROOT_SLOTS
from sleap_roots_training.registry.chooser import MODE_VOCAB, SPECIES_VOCAB

#: Root-type vocabulary, mirroring the selection matrix's root slots.
ROOT_TYPE_VOCAB = frozenset(_ROOT_SLOTS)

#: Recognized ``sleap-nn`` top-level config keys (``TrainingJobConfig``). Any other
#: top-level key besides our ``experiment`` block is rejected, not silently dropped.
_SLEAP_NN_KEYS = frozenset(
    {
        "data_config",
        "model_config",
        "trainer_config",
        "name",
        "description",
        "sleap_nn_version",
        "filename",
    }
)

_EXPERIMENT_KEY = "experiment"

#: Returned (not raised) when the ``train`` extra is absent: the base-safe checks still
#: pass while signaling that deep backend validation did not run (a skip is not a failure).
_SKIP_NOTE = (
    "deep sleap-nn validation skipped — install the 'train' extra "
    "(pip install 'sleap-roots-training[train]') for full backend validation"
)


class ConfigError(ValueError):
    """A training config failed to load or validate; the message names the bad field."""


@dataclass
class DatasetConfig:
    """Identity of the plain, local ``.slp`` dataset an experiment trains on."""

    name: str = MISSING
    path: str = MISSING
    notes: str = ""


@dataclass
class ExperimentConfig:
    """Repo-owned experiment metadata that sleap-nn's config has no concept of."""

    species: str = MISSING
    mode: str = MISSING
    root_type: str = MISSING
    dataset: DatasetConfig = field(default_factory=DatasetConfig)


def load_config(path: Union[str, Path]) -> DictConfig:
    """Load a training-config YAML into an OmegaConf mapping.

    Args:
        path: Path to the config file.

    Returns:
        The loaded config as an OmegaConf ``DictConfig``.

    Raises:
        ConfigError: The file is unreadable, empty, or not parseable as a YAML mapping.
    """
    path = Path(path)
    try:
        cfg = OmegaConf.load(path)
    except (OmegaConfBaseException, yaml.YAMLError, OSError) as err:
        raise ConfigError(f"could not parse config {path}: {err}") from err
    if cfg is None or not OmegaConf.is_dict(cfg) or len(cfg) == 0:
        raise ConfigError(f"config {path} is empty or not a YAML mapping")
    return cfg


def validate_config(cfg: DictConfig) -> list[str]:
    """Validate a loaded training config, returning a list of informational notes.

    The experiment-metadata, explicit-seed, and W&B-enablement pairing checks always run
    (base-install safe). Deep ``sleap-nn`` validation runs when the ``train`` extra is
    importable; otherwise a skip note is returned (a skip is not a failure).

    Args:
        cfg: A config mapping, as returned by :func:`load_config`.

    Returns:
        Informational notes (e.g. that deep validation was skipped); empty when the
        backend validated the config fully.

    Raises:
        ConfigError: Any check fails; the message names the offending field.
    """
    _check_top_level_keys(cfg)
    _validate_experiment(cfg)
    _check_seed(cfg)
    _check_wandb(cfg)
    if _deep_validation_available():
        _deep_validate(cfg)
        return []
    return [_SKIP_NOTE]


def to_sleap_nn_config(cfg: DictConfig) -> DictConfig:
    """Return the resolved sleap-nn-native config (the ``experiment`` block stripped).

    Merges the sleap-nn portion onto ``OmegaConf.structured(TrainingJobConfig())`` so
    schema defaults — notably ``data_config.preprocessing`` — are **materialized**,
    which prevents sleap-nn 0.2.0's post-fit ``ConfigAttributeError`` on a config that
    omitted ``preprocessing``. Requires the ``train`` extra (imports ``sleap_nn``).

    Args:
        cfg: A config mapping, as returned by :func:`load_config`.

    Returns:
        The fully-resolved ``sleap-nn`` config, ready for ``sleap-nn train --config``.
    """
    from sleap_nn.config.training_job_config import TrainingJobConfig

    schema = OmegaConf.structured(TrainingJobConfig())
    return OmegaConf.merge(schema, _strip_experiment(cfg))


# --- internal helpers ------------------------------------------------------------------


def _strip_experiment(cfg: DictConfig) -> DictConfig:
    """Return a copy of ``cfg`` without the ``experiment`` block (the sleap-nn portion)."""
    keys = [key for key in cfg.keys() if key != _EXPERIMENT_KEY]
    return OmegaConf.masked_copy(cfg, keys)


def _check_top_level_keys(cfg: DictConfig) -> None:
    """Reject any top-level key that is neither ``experiment`` nor a sleap-nn block."""
    allowed = _SLEAP_NN_KEYS | {_EXPERIMENT_KEY}
    unknown = sorted(key for key in cfg.keys() if key not in allowed)
    if unknown:
        raise ConfigError(
            f"unrecognized top-level key(s): {', '.join(unknown)} "
            "(expected 'experiment' or a sleap-nn block)"
        )


def _validate_experiment(cfg: DictConfig) -> None:
    """Validate the ``experiment`` block against the schema and the vocabularies."""
    if _EXPERIMENT_KEY not in cfg:
        raise ConfigError("missing required top-level 'experiment' block")
    schema = OmegaConf.structured(ExperimentConfig)
    try:
        merged = OmegaConf.merge(schema, cfg.experiment)
        OmegaConf.to_container(merged, resolve=True, throw_on_missing=True)
    except OmegaConfBaseException as err:
        raise ConfigError(f"invalid 'experiment' block: {err}") from err
    _check_vocab("experiment.species", merged.species, SPECIES_VOCAB)
    _check_vocab("experiment.mode", merged.mode, MODE_VOCAB)
    _check_vocab("experiment.root_type", merged.root_type, ROOT_TYPE_VOCAB)


def _check_vocab(field_name: str, value: str, vocab: frozenset) -> None:
    """Raise if ``value`` is outside ``vocab``, naming the field and allowed values."""
    if value not in vocab:
        allowed = ", ".join(sorted(vocab))
        raise ConfigError(f"invalid {field_name}: {value!r} (allowed: {allowed})")


def _check_seed(cfg: DictConfig) -> None:
    """Require an explicit integer ``trainer_config.seed`` (0.2.0 has no default)."""
    seed = OmegaConf.select(cfg, "trainer_config.seed", default=None)
    if seed is None:
        raise ConfigError(
            "trainer_config.seed is required (sleap-nn 0.2.0 has no default seed); "
            "set an explicit integer seed so a baseline is reproducible"
        )
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ConfigError(f"trainer_config.seed must be an integer, got {seed!r}")


def _check_wandb(cfg: DictConfig) -> None:
    """When ``trainer_config.use_wandb`` is true, require ``wandb.entity`` + ``project``."""
    if not OmegaConf.select(cfg, "trainer_config.use_wandb", default=False):
        return
    for key in ("entity", "project"):
        value = OmegaConf.select(cfg, f"trainer_config.wandb.{key}", default=None)
        if not value:
            raise ConfigError(
                f"trainer_config.use_wandb is true but trainer_config.wandb.{key} is "
                "not set"
            )


def _deep_validation_available() -> bool:
    """Whether the ``sleap_nn`` backend is importable (a monkeypatchable test seam)."""
    return importlib.util.find_spec("sleap_nn") is not None


def _deep_validate(cfg: DictConfig) -> None:
    """Delegate validation of the sleap-nn portion to sleap-nn. Requires the train extra."""
    from sleap_nn.config.training_job_config import verify_training_cfg

    try:
        verify_training_cfg(_strip_experiment(cfg))
    except Exception as err:  # sleap-nn raises ValueError / OmegaConf errors
        raise ConfigError(f"sleap-nn backend validation failed: {err}") from err
