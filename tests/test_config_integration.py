"""Integration tests for the deep sleap-nn delegation path (require the ``train`` extra).

These exercise ``to_sleap_nn_config`` (``data_config.preprocessing`` materialization) and
the delegated ``verify_training_cfg`` structural check (backbone/head must-be-set). They
are ``@pytest.mark.integration`` (deselected by CI's ``-m "not integration"``) and
``importorskip`` on ``sleap_nn`` in the body, so they never break collection on the base
matrix. They are run manually on a ``[train]``-installed box (see the change's tasks.md 5.8),
which is the only place the anti-crash guarantee is actually exercised.
"""

from __future__ import annotations

import pytest

from sleap_roots_training import config

pytestmark = pytest.mark.integration


def test_to_sleap_nn_config_materializes_preprocessing(write_config):
    pytest.importorskip("sleap_nn")
    path = write_config(drop=("data_config.preprocessing",))
    resolved = config.to_sleap_nn_config(config.load_config(path))
    assert "preprocessing" in resolved.data_config
    assert len(resolved.data_config.preprocessing) > 0


def test_no_backbone_or_head_fails_via_sleap_nn(write_config):
    pytest.importorskip("sleap_nn")
    path = write_config(
        drop=("model_config.backbone_config", "model_config.head_configs")
    )
    with pytest.raises(config.ConfigError):
        config.validate_config(config.load_config(path))


def test_full_valid_config_passes_deep_validation(write_config):
    pytest.importorskip("sleap_nn")
    # VALID_CONFIG names a backbone + head + seed, so deep validation returns no notes.
    assert config.validate_config(config.load_config(write_config())) == []
