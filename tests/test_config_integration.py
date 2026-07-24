"""Integration tests for the deep sleap-nn delegation path (require the ``train`` extra).

These exercise the delegated ``verify_training_cfg`` structural check (backbone/head
must-be-set) and that a fully-valid config passes deep validation. They are
``@pytest.mark.integration`` (deselected by CI's ``-m "not integration"``) and
``importorskip`` on ``sleap_nn`` in the body, so they never break collection on the base
matrix. They are run manually on a ``[train]``-installed box (see the change's tasks.md 5.8),
the only place the delegated backend validation is actually exercised.
"""

from __future__ import annotations

import pytest

from sleap_roots_training import config

pytestmark = pytest.mark.integration


def test_no_backbone_or_head_fails_via_sleap_nn(write_config):
    pytest.importorskip("sleap_nn")
    path = write_config(
        drop=("model_config.backbone_config", "model_config.head_configs")
    )
    # sleap-nn's own check_must_be_set message ("BackboneConfig: At least one attribute
    # ... must be set") — case-insensitive so "BackboneConfig"/"HeadConfig" both match.
    with pytest.raises(config.ConfigError, match=r"(?i)backbone|head"):
        config.validate_config(config.load_config(path))


def test_full_valid_config_passes_deep_validation(write_config):
    pytest.importorskip("sleap_nn")
    # VALID_CONFIG names a backbone + head + seed + preprocessing, so deep validation
    # runs and returns no notes.
    assert config.validate_config(config.load_config(write_config())) == []


def test_sleap_nn_keys_match_training_job_config():
    # Mechanically catch drift between our hand-maintained _SLEAP_NN_KEYS and the real
    # TrainingJobConfig top-level fields (only checkable where sleap_nn is installed).
    pytest.importorskip("sleap_nn")
    import attrs
    from sleap_nn.config.training_job_config import TrainingJobConfig

    real = {f.name for f in attrs.fields(TrainingJobConfig)}
    assert config._SLEAP_NN_KEYS == real, (
        f"_SLEAP_NN_KEYS drifted: missing={real - config._SLEAP_NN_KEYS}, "
        f"extra={config._SLEAP_NN_KEYS - real}"
    )
