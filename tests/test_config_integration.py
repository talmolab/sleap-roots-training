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
    with pytest.raises(config.ConfigError, match="backbone|head"):
        config.validate_config(config.load_config(path))


def test_full_valid_config_passes_deep_validation(write_config):
    pytest.importorskip("sleap_nn")
    # VALID_CONFIG names a backbone + head + seed + preprocessing, so deep validation
    # runs and returns no notes.
    assert config.validate_config(config.load_config(write_config())) == []
